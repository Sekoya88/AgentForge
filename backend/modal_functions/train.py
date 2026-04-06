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

    # Strip hf:// prefix — load_dataset expects "org/dataset", not "hf://org/dataset"
    if dataset_path.startswith("hf://"):
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
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=2048,
            load_in_4bit=True,
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
    eval_dataset = None
    try:
        if looks_like_hub:
            full = _load_hub_full()
        else:
            full = load_dataset(dataset_path)
        if "test" in full:
            dataset = full["train"]
            eval_dataset = full["test"]
        elif "validation" in full:
            dataset = full["train"]
            eval_dataset = full["validation"]
        else:
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
        max_seq_length=2048,
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


@app.function(image=speech_stub_image, timeout=600)
def train_speech_model(
    job_id: str,
    modality: str,
    base_model: str,
    dataset_path: str,
    hyperparams: dict,
) -> str:
    """Stub ASR/TTS training: writes live metrics then a final row with ``inference_endpoint``.

    Real HF Whisper / XTTS training can replace this body later. Deploy with the same
    command as LLM training: ``modal deploy backend/modal_functions/train.py``.
    """
    import time

    _ = base_model, dataset_path, hyperparams
    md = modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
    md[job_id] = {
        "step": 1,
        "loss": 0.0,
        "epoch": 1,
        "status": "running",
        "modality": modality,
    }
    time.sleep(2)
    if modality == "whisper":
        endpoint = f"https://stub-speech.agentforge/transcribe/{job_id}"
    elif modality == "tts_voice":
        endpoint = f"https://stub-speech.agentforge/synthesize/{job_id}"
    else:
        endpoint = f"https://stub-speech.agentforge/speech/{job_id}"

    final = {
        "step": 10,
        "loss": 0.01,
        "epoch": 1,
        "status": "completed",
        "model_output_path": f"/data/speech/{job_id}",
        "inference_endpoint": endpoint,
        "modality": modality,
    }
    md[job_id] = final
    return endpoint
