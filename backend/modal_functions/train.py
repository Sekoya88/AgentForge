import modal

app = modal.App("agentforge-finetune")
metrics_dict = modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
data_volume = modal.Volume.from_name("agentforge-datasets", create_if_missing=True)

# Optional HuggingFace secret — only included if it exists in Modal
try:
    _hf_secrets = [modal.Secret.from_name("huggingface-secret")]
except Exception:
    _hf_secrets = []

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    # Pin numpy>=2.2 first — 2.1.x has a recursive import bug in numpy.dtypes
    .pip_install("numpy>=2.2.0,<3")
    .pip_install(
        "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git",
        "trl",
        "transformers",
        "datasets",
        "accelerate",
        "peft",
        "bitsandbytes",
        "torch",
        "torchvision",
    )
)

# Lightweight CPU stub for speech jobs (whisper / tts_voice) — same app as LLM SFT.
speech_stub_image = modal.Image.debian_slim(python_version="3.12").pip_install("modal")


@app.function(
    image=image,
    gpu="A10G",
    timeout=10800,
    volumes={"/data": data_volume},
    secrets=_hf_secrets,
)
def train_model(job_id: str, base_model: str, dataset_path: str, hyperparams: dict):
    import os
    import random
    import time

    # Disable Unsloth telemetry — it tries to reach HuggingFace for 120s and
    # times out on Modal's network, crashing the entire training run.
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    # Reduce CUDA memory fragmentation — helps avoid OOM during checkpoint/eval
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    # Forward HuggingFace token for gated/private models (injected via Modal secret)
    if hf_token := os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN"):
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

    # Monkey-patch the statistics call that causes the timeout
    import unsloth.models._utils as _unsloth_utils
    from unsloth import FastLanguageModel, is_bfloat16_supported

    _unsloth_utils.get_statistics = lambda *args, **kwargs: None

    import modal
    from datasets import load_dataset
    from transformers import EarlyStoppingCallback, TrainerCallback
    from trl import SFTConfig, SFTTrainer

    # ─── Callbacks ───────────────────────────────────────────────────────

    class MetricsCallback(TrainerCallback):
        """Push live metrics to Modal Dict for backend polling."""

        def __init__(self, job_id: str):
            self.job_id = job_id
            self.metrics_dict = modal.Dict.from_name("agentforge-metrics")
            self._start_time = None

        def on_train_begin(self, args, state, control, **kwargs):
            self._start_time = time.time()

        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and "loss" in logs:
                elapsed = time.time() - self._start_time if self._start_time else 0
                speed = elapsed / state.global_step if state.global_step > 0 else 0
                remaining = (
                    speed * (state.max_steps - state.global_step) if state.max_steps > 0 else 0
                )
                self.metrics_dict[self.job_id] = {
                    "loss": logs["loss"],
                    "grad_norm": logs.get("grad_norm"),
                    "learning_rate": logs.get("learning_rate"),
                    "epoch": logs.get("epoch"),
                    "step": state.global_step,
                    "total_steps": state.max_steps,
                    "elapsed_seconds": round(elapsed, 1),
                    "eta_seconds": round(remaining, 1),
                    "speed_spit": round(speed, 2),
                }
            # Also capture eval metrics (eval_loss)
            if logs and "eval_loss" in logs:
                self.metrics_dict[f"{self.job_id}:eval"] = {
                    "eval_loss": logs["eval_loss"],
                    "step": state.global_step,
                }

    class SampleInferenceCallback(TrainerCallback):
        """Run a sample inference at each checkpoint to show how the model evolves."""

        def __init__(self, job_id: str, tokenizer, eval_prompts: list[str]):
            self.job_id = job_id
            self.tokenizer = tokenizer
            self.eval_prompts = eval_prompts
            self.metrics_dict = modal.Dict.from_name("agentforge-metrics")

        def on_save(self, args, state, control, **kwargs):
            model = kwargs.get("model")
            if model is None or not self.eval_prompts:
                return
            # Pick a random prompt
            prompt = random.choice(self.eval_prompts)
            try:
                FastLanguageModel.for_inference(model)
                inputs = self.tokenizer(prompt, return_tensors="pt").to(model.device)
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=64,
                    temperature=0.7,
                    do_sample=True,
                )
                generated = outputs[0][inputs["input_ids"].shape[1] :]
                response = self.tokenizer.decode(generated, skip_special_tokens=True)
                # Put model back in training mode
                model.train()

                # Store sample in Dict
                samples_key = f"{self.job_id}:samples"
                existing = []
                try:
                    existing = self.metrics_dict[samples_key]
                except KeyError:
                    pass
                existing.append(
                    {
                        "step": state.global_step,
                        "prompt": prompt[:200],
                        "response": response[:500],
                    }
                )
                self.metrics_dict[samples_key] = existing
                print(f"\n[Checkpoint step {state.global_step}] Sample inference:")
                print(f"  Prompt: {prompt[:100]}...")
                print(f"  Response: {response[:200]}")
                print()
            except Exception as e:
                print(f"[Checkpoint] Sample inference failed: {e}")

    # ─── Dataset loading ─────────────────────────────────────────────────

    def _parse_hf_repo_config(hub_path: str) -> tuple[str, str | None]:
        """Resolve HuggingFace hub id and optional config name.

        - Explicit: ``org/dataset/config`` → repo ``org/dataset``, config ``config``
          (e.g. ``openai/gsm8k/main`` or ``openai/gsm8k/socratic``).
        - If the dataset advertises multiple configs and none is in the path, pick
          ``main`` when listed, else the first config (gsm8k: main vs socratic).
        """
        parts = [p for p in hub_path.split("/") if p]
        if len(parts) >= 3:
            return "/".join(parts[:-1]), parts[-1]
        repo = "/".join(parts)
        try:
            from datasets import get_dataset_config_names

            names = list(get_dataset_config_names(repo))
        except Exception:
            return repo, None
        if not names:
            return repo, None
        if len(names) == 1:
            return repo, names[0]
        chosen = "main" if "main" in names else names[0]
        print(
            f"Dataset '{repo}' has multiple configs {names}; using '{chosen}'. "
            f"Override with hf://{repo}/<config> (e.g. hf://openai/gsm8k/socratic)."
        )
        return repo, chosen

    # Strip hf:// and optional hf://datasets/ prefix
    # load_dataset expects "org/dataset", not "hf://org/dataset" or "hf://datasets/org/dataset"
    if dataset_path.startswith("hf://datasets/"):
        dataset_path = dataset_path[len("hf://datasets/") :]
    elif dataset_path.startswith("hf://"):
        dataset_path = dataset_path[len("hf://") :]

    looks_like_hub = (
        "/" in dataset_path
        and not dataset_path.startswith("/")
        and not dataset_path.endswith((".json", ".jsonl", ".csv"))
    )
    hf_repo, hf_config = (dataset_path, None)
    if looks_like_hub:
        hf_repo, hf_config = _parse_hf_repo_config(dataset_path)

    # Normalize model ID — strip accidental leading "org/" (3-segment paths like
    # "org/LiquidAI/LFM2.5-1.2B" become "LiquidAI/LFM2.5-1.2B")
    _parts = base_model.split("/")
    if len(_parts) == 3 and _parts[0].lower() == "org":
        base_model = "/".join(_parts[1:])
        print(f"Normalized model name to: {base_model}")

    print(f"Starting training for job {job_id} with model {base_model}")

    _use_unsloth = True
    _max_seq_length = hyperparams.get("max_seq_length", 1024)
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=_max_seq_length,
            load_in_4bit=True,
            # Force eager attention — FlexAttention (used by LFM2/hybrid archs)
            # allocates a full attention score matrix during eval and OOMs on A10G.
            attn_implementation="eager",
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            target_modules=[
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
            lora_alpha=16,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=3407,
        )
    except (RuntimeError, ValueError) as _unsloth_err:
        print(
            f"Unsloth cannot load this architecture ({_unsloth_err}). "
            "Falling back to transformers + PEFT."
        )
        _use_unsloth = False
        import torch
        from peft import LoraConfig, TaskType
        from peft import get_peft_model as _peft_get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        _bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16
            if torch.cuda.is_bf16_supported()
            else torch.float16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=_bnb,
            device_map="auto",
        )
        tokenizer = AutoTokenizer.from_pretrained(base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        _lora = LoraConfig(
            r=16,
            lora_alpha=16,
            # Use only attention projections; gate/up/down may not exist in all archs
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            lora_dropout=0,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = _peft_get_peft_model(model, _lora)
        model.print_trainable_parameters()

    def _load_hub_full() -> dict:
        if hf_config is not None:
            return load_dataset(hf_repo, hf_config)
        return load_dataset(hf_repo)

    def _load_hub_train_split():
        if hf_config is not None:
            return load_dataset(hf_repo, hf_config, split="train")
        return load_dataset(hf_repo, split="train")

    # Try loading with train+test split; fall back to train-only
    # eval_dataset disabled: running eval during training doubles GPU memory
    # usage at each checkpoint (especially with FlexAttention-based models like LFM2).
    # Training loss alone is sufficient to monitor convergence.
    eval_dataset = None
    try:
        if looks_like_hub:
            full = _load_hub_full()
        else:
            full = load_dataset(dataset_path)
        dataset = full["train"]
    except Exception:
        try:
            if looks_like_hub:
                dataset = _load_hub_train_split()
            else:
                dataset = load_dataset(dataset_path, split="train")
        except Exception:
            if dataset_path.endswith(".json") or dataset_path.endswith(".jsonl"):
                dataset = load_dataset("json", data_files=dataset_path, split="train")
            elif dataset_path.endswith(".csv"):
                dataset = load_dataset("csv", data_files=dataset_path, split="train")
            elif looks_like_hub:
                dataset = _load_hub_train_split()
            else:
                dataset = load_dataset(dataset_path, split="train")

    # If no eval split, carve 5% from train (min 10 rows)
    if eval_dataset is None and len(dataset) > 50:
        split = dataset.train_test_split(test_size=0.05, seed=42)
        dataset = split["train"]
        eval_dataset = split["test"]
        print(f"Auto-split: {len(dataset)} train / {len(eval_dataset)} eval")

    # ─── Normalise dataset into "text" column ────────────────────────────

    def normalise_dataset(ds):
        columns = set(ds.column_names)

        if "text" in columns:
            return ds

        if "messages" in columns or "conversations" in columns:
            msg_col = "messages" if "messages" in columns else "conversations"
            if tokenizer.chat_template is None:
                tokenizer.chat_template = (
                    "{% for message in messages %}"
                    "{{ '<|' + message['role'] + '|>\\n' + message['content'] + '\\n' }}"
                    "{% endfor %}"
                )

            def _map_chat(example):
                convo = example[msg_col]
                normalised = []
                for msg in convo:
                    role = msg.get("role") or msg.get("from", "user")
                    content = msg.get("content") or msg.get("value", "")
                    if role in ("human",):
                        role = "user"
                    elif role in ("gpt", "bot"):
                        role = "assistant"
                    normalised.append({"role": role, "content": content})
                example["text"] = tokenizer.apply_chat_template(
                    normalised, tokenize=False, add_generation_prompt=False
                )
                return example

            return ds.map(_map_chat, remove_columns=[msg_col])

        if "question" in columns and "answer" in columns:

            def _map_qa(example):
                q = example["question"]
                a = example["answer"]
                example["text"] = f"### Question:\n{q}\n\n### Answer:\n{a}"
                return example

            return ds.map(_map_qa, remove_columns=["question", "answer"])

        if "instruction" in columns:

            def _map_alpaca(example):
                inp = example.get("input", "")
                out = example.get("output", "")
                instr = example["instruction"]
                if inp:
                    example["text"] = (
                        f"### Instruction:\n{instr}\n\n### Input:\n{inp}\n\n### Response:\n{out}"
                    )
                else:
                    example["text"] = f"### Instruction:\n{instr}\n\n### Response:\n{out}"
                return example

            cols_to_remove = [c for c in ["instruction", "input", "output"] if c in columns]
            return ds.map(_map_alpaca, remove_columns=cols_to_remove)

        # Fallback
        first_col = ds.column_names[0]
        return ds.rename_column(first_col, "text")

    dataset = normalise_dataset(dataset)
    print(f"Train: {len(dataset)} examples. Columns: {dataset.column_names}")

    if eval_dataset is not None:
        eval_dataset = normalise_dataset(eval_dataset)
        print(f"Eval: {len(eval_dataset)} examples.")

    # ─── Build eval prompts for sample inference ─────────────────────────

    eval_prompts = []
    sample_source = eval_dataset if eval_dataset is not None else dataset
    indices = random.sample(range(len(sample_source)), min(10, len(sample_source)))
    for idx in indices:
        text = sample_source[idx]["text"]
        # Take the first ~200 chars as a prompt prefix
        if len(text) > 100:
            eval_prompts.append(text[:200])
    print(f"Prepared {len(eval_prompts)} eval prompts for sample inference at checkpoints.")

    # ─── Training config ─────────────────────────────────────────────────

    max_steps = hyperparams.get("max_steps", 60)
    learning_rate = hyperparams.get("learning_rate", 2e-4)
    batch_size = hyperparams.get("batch_size", 2)
    epochs = hyperparams.get("epochs", None)
    patience = hyperparams.get("patience", 3)

    # Checkpoint every 20% of training (min every 10 steps)
    total = int(epochs * len(dataset) / (batch_size * 4)) if epochs else max_steps
    save_steps = max(10, total // 5)
    eval_steps = save_steps

    sft_config_kwargs = {
        "per_device_train_batch_size": batch_size,
        "gradient_accumulation_steps": 4,
        "warmup_steps": 10,
        "learning_rate": learning_rate,
        "fp16": not is_bfloat16_supported(),
        "bf16": is_bfloat16_supported(),
        "logging_steps": 1,
        "optim": "adamw_8bit",
        "output_dir": f"/data/outputs/{job_id}",
        "dataset_text_field": "text",
        "save_steps": save_steps,
        "save_total_limit": 3,
        "load_best_model_at_end": eval_dataset is not None,
        "metric_for_best_model": "eval_loss" if eval_dataset is not None else None,
        "greater_is_better": False if eval_dataset is not None else None,
    }

    if eval_dataset is not None:
        sft_config_kwargs["eval_strategy"] = "steps"
        sft_config_kwargs["eval_steps"] = eval_steps

    if epochs is not None:
        sft_config_kwargs["num_train_epochs"] = epochs
    else:
        sft_config_kwargs["max_steps"] = max_steps

    # ─── Callbacks ───────────────────────────────────────────────────────

    callbacks = [MetricsCallback(job_id)]

    if eval_dataset is not None and patience > 0:
        callbacks.append(EarlyStoppingCallback(early_stopping_patience=patience))
        print(f"Early stopping enabled: patience={patience} eval checks")

    if eval_prompts:
        callbacks.append(SampleInferenceCallback(job_id, tokenizer, eval_prompts))

    # ─── Train ───────────────────────────────────────────────────────────

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        eval_dataset=eval_dataset,
        max_seq_length=_max_seq_length,
        args=SFTConfig(**sft_config_kwargs),
        callbacks=callbacks,
    )

    print(f"Config: save_steps={save_steps}, eval_steps={eval_steps}, patience={patience}")
    trainer.train()

    # ─── Save final model ────────────────────────────────────────────────

    output_model_path = f"/data/models/{job_id}"
    if _use_unsloth:
        model.save_pretrained_merged(output_model_path, tokenizer, save_method="merged_16bit")
    else:
        model.save_pretrained(output_model_path)
        tokenizer.save_pretrained(output_model_path)

    # ─── Final metrics ───────────────────────────────────────────────────

    final_metrics = {
        "loss": 0.0,
        "epoch": epochs,
        "step": max_steps if epochs is None else total,
        "status": "completed",
        "model_output_path": output_model_path,
    }

    # Attach sample inferences if any
    try:
        samples = modal.Dict.from_name("agentforge-metrics")[f"{job_id}:samples"]
        final_metrics["samples"] = samples
    except KeyError:
        pass

    metrics_dict = modal.Dict.from_name("agentforge-metrics")
    metrics_dict[job_id] = final_metrics

    print(f"Training completed for job {job_id}. Model saved to {output_model_path}")
    return output_model_path


# ── Speech training images ────────────────────────────────────────────────────

whisper_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install(
        "numpy>=2.2.0,<3",
        "torch",
        "torchaudio",
        "transformers>=4.40.0",
        "datasets",
        "accelerate",
        "soundfile",
        "librosa",
        "evaluate",
        "jiwer",  # WER metric for Whisper
    )
)

xtts_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg", "libsndfile1", "espeak-ng")
    .pip_install(
        "numpy>=2.2.0,<3",
        "torch",
        "torchaudio",
        "TTS>=0.22.0",  # Coqui TTS — includes XTTS-v2
        "soundfile",
        "librosa",
    )
)


# ── Whisper fine-tune ─────────────────────────────────────────────────────────


@app.function(
    image=whisper_image,
    gpu="A10G",
    timeout=7200,
    volumes={"/data": data_volume},
    secrets=_hf_secrets,
)
def _train_whisper(job_id: str, base_model: str, dataset_path: str, hyperparams: dict) -> str:
    """Fine-tune a Whisper model for ASR using HuggingFace Seq2SeqTrainer."""
    import os
    from dataclasses import dataclass
    from typing import Any

    import evaluate
    import modal
    import torch
    from datasets import Audio, load_dataset
    from transformers import (
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
        TrainerCallback,
        WhisperForConditionalGeneration,
        WhisperProcessor,
    )

    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    if hf_token := os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN"):
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

    md = modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
    md[job_id] = {"step": 0, "loss": None, "status": "loading", "modality": "whisper"}

    # Default to whisper-small if not specified
    model_id = base_model if "whisper" in base_model.lower() else "openai/whisper-small"
    language = hyperparams.get("language", "en")
    task = hyperparams.get("task", "transcribe")
    max_steps = hyperparams.get("max_steps", 500)
    batch_size = hyperparams.get("batch_size", 8)
    learning_rate = hyperparams.get("learning_rate", 1e-5)

    print(f"[Whisper] Loading model {model_id}, language={language}, task={task}")
    processor = WhisperProcessor.from_pretrained(model_id, language=language, task=task)
    model = WhisperForConditionalGeneration.from_pretrained(model_id)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []

    # Load dataset — expects audio + sentence/transcription columns
    print(f"[Whisper] Loading dataset from {dataset_path}")
    try:
        if dataset_path.startswith("hf://"):
            dataset_path = dataset_path.removeprefix("hf://datasets/").removeprefix("hf://")
        ds = load_dataset(
            dataset_path, split="train+validation" if "+" in dataset_path else "train"
        )
    except Exception:
        ds = load_dataset(dataset_path, split="train")

    ds = ds.cast_column("audio", Audio(sampling_rate=16_000))

    text_col = next(
        (c for c in ["sentence", "transcription", "text", "transcript"] if c in ds.column_names),
        ds.column_names[0],
    )

    def prepare_batch(batch):
        audio = [a["array"] for a in batch["audio"]]
        batch["input_features"] = processor(
            audio, sampling_rate=16_000, return_tensors="np"
        ).input_features
        batch["labels"] = processor.tokenizer(batch[text_col]).input_ids
        return batch

    ds = ds.map(prepare_batch, remove_columns=ds.column_names, batched=True, batch_size=8)
    split = ds.train_test_split(test_size=0.05, seed=42)

    wer_metric = evaluate.load("wer")

    @dataclass
    class DataCollatorSpeechSeq2SeqWithPadding:
        processor: Any

        def __call__(self, features):
            input_features = [{"input_features": f["input_features"]} for f in features]
            batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")
            label_features = [{"input_ids": f["labels"]} for f in features]
            labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
            labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
            if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
                labels = labels[:, 1:]
            batch["labels"] = labels
            return batch

    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)

    def compute_metrics(pred):
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
        pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        wer = 100 * wer_metric.compute(predictions=pred_str, references=label_str)
        return {"wer": wer}

    class WhisperMetricsCallback(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs:
                md[job_id] = {
                    "step": state.global_step,
                    "loss": logs.get("loss"),
                    "wer": logs.get("eval_wer"),
                    "status": "training",
                    "modality": "whisper",
                }

    output_dir = f"/data/speech/{job_id}"
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=2,
        learning_rate=learning_rate,
        warmup_steps=50,
        max_steps=max_steps,
        fp16=torch.cuda.is_available(),
        eval_strategy="steps",
        eval_steps=max_steps // 5,
        save_steps=max_steps // 5,
        save_total_limit=2,
        logging_steps=10,
        predict_with_generate=True,
        generation_max_length=225,
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        push_to_hub=False,
        report_to="none",
    )

    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        processing_class=processor.feature_extractor,
        callbacks=[WhisperMetricsCallback()],
    )

    print(f"[Whisper] Starting training: {max_steps} steps")
    trainer.train()
    trainer.save_model(output_dir)
    processor.save_pretrained(output_dir)
    print(f"[Whisper] Saved to {output_dir}")
    return output_dir


# ── XTTS voice cloning ────────────────────────────────────────────────────────


@app.function(
    image=xtts_image,
    gpu="A10G",
    timeout=3600,
    volumes={"/data": data_volume},
)
def _train_xtts_voice(job_id: str, dataset_path: str, hyperparams: dict) -> str:
    """Fine-tune XTTS-v2 for voice cloning from a set of audio samples."""
    import os

    import modal
    from TTS.api import TTS

    os.environ["COQUI_TOS_AGREED"] = "1"

    md = modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
    md[job_id] = {"step": 0, "status": "loading", "modality": "tts_voice"}

    output_dir = f"/data/speech/{job_id}"
    os.makedirs(output_dir, exist_ok=True)

    # XTTS-v2 supports zero-shot voice cloning from reference audio.
    # For production cloning, we synthesize a reference embedding from the uploaded samples.
    print("[XTTS] Loading XTTS-v2 model")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

    # Collect reference wav files from the volume dataset path
    import glob

    wav_files = glob.glob(f"{dataset_path}/**/*.wav", recursive=True)
    if not wav_files:
        wav_files = glob.glob(f"{dataset_path}/*.wav")
    if not wav_files:
        raise RuntimeError(f"No .wav files found in {dataset_path}")

    md[job_id] = {
        "step": 1,
        "total": len(wav_files),
        "status": "computing_embedding",
        "modality": "tts_voice",
    }
    print(f"[XTTS] Found {len(wav_files)} reference audio files, computing speaker embedding")

    # Compute speaker latent from the reference samples
    import json

    import torch

    # Use the XTTS synthesizer to extract the speaker embedding
    gpt_cond_latent, speaker_embedding = tts.synthesizer.tts_model.get_conditioning_latents(
        audio_path=wav_files
    )
    torch.save(
        {
            "gpt_cond_latent": gpt_cond_latent,
            "speaker_embedding": speaker_embedding,
        },
        os.path.join(output_dir, "speaker.pt"),
    )

    # Save metadata
    meta = {
        "job_id": job_id,
        "modality": "tts_voice",
        "model": "xtts_v2",
        "num_reference_files": len(wav_files),
        "output_dir": output_dir,
    }
    with open(os.path.join(output_dir, "meta.json"), "w") as f:
        json.dump(meta, f)

    md[job_id] = {
        "step": len(wav_files),
        "total": len(wav_files),
        "status": "completed",
        "modality": "tts_voice",
        "model_output_path": output_dir,
    }
    print(f"[XTTS] Speaker embedding saved to {output_dir}")
    return output_dir


# ── Unified speech router ─────────────────────────────────────────────────────


@app.function(image=speech_stub_image, timeout=300)
def train_speech_model(
    job_id: str,
    modality: str,
    base_model: str,
    dataset_path: str,
    hyperparams: dict,
) -> str:
    """Route speech training to the correct GPU function based on modality.

    modality == "whisper"   → fine-tune Whisper ASR (Seq2SeqTrainer)
    modality == "tts_voice" → XTTS-v2 speaker embedding from reference audio
    """
    import modal as _modal

    md = _modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
    md[job_id] = {"step": 0, "status": "dispatching", "modality": modality}

    if modality == "whisper":
        output_dir = _train_whisper.remote(job_id, base_model, dataset_path, hyperparams)
    elif modality == "tts_voice":
        output_dir = _train_xtts_voice.remote(job_id, dataset_path, hyperparams)
    else:
        raise ValueError(
            f"Unknown speech modality: {modality!r}. Expected 'whisper' or 'tts_voice'."
        )

    # Register a Modal web endpoint for inference so the backend can use it
    from modal import web_endpoint as _web_endpoint  # noqa: F401

    # The inference endpoint is served by inference.py (already deployed separately).
    # Return a synthetic endpoint URL that the inference function can route.
    endpoint = f"modal://agentforge-speech/{modality}/{job_id}"

    md[job_id] = {
        "status": "completed",
        "modality": modality,
        "model_output_path": output_dir,
        "inference_endpoint": endpoint,
    }
    return endpoint
