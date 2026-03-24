import modal

app = modal.App("agentforge-finetune")
metrics_dict = modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
data_volume = modal.Volume.from_name("agentforge-datasets", create_if_missing=True)

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


@app.function(image=image, gpu="A10G", timeout=3600, volumes={"/data": data_volume})
def train_model(job_id: str, base_model: str, dataset_path: str, hyperparams: dict):
    import os

    # Disable Unsloth telemetry — it tries to reach HuggingFace for 120s and
    # times out on Modal's network, crashing the entire training run.
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    # Monkey-patch the statistics call that causes the timeout
    import unsloth.models._utils as _unsloth_utils
    from unsloth import FastLanguageModel, is_bfloat16_supported

    _unsloth_utils.get_statistics = lambda *args, **kwargs: None

    import modal
    from datasets import load_dataset
    from transformers import TrainerCallback
    from trl import SFTConfig, SFTTrainer

    class MetricsCallback(TrainerCallback):
        def __init__(self, job_id: str):
            self.job_id = job_id
            # Reload dict to ensure reference is active
            self.metrics_dict = modal.Dict.from_name("agentforge-metrics")

        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and "loss" in logs:
                self.metrics_dict[self.job_id] = {
                    "loss": logs["loss"],
                    "epoch": logs.get("epoch"),
                    "step": state.global_step,
                }

    # Strip hf:// prefix — load_dataset expects "org/dataset", not "hf://org/dataset"
    if dataset_path.startswith("hf://"):
        dataset_path = dataset_path[len("hf://") :]

    print(f"Starting training for job {job_id} with model {base_model}")

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

    try:
        dataset = load_dataset(dataset_path, split="train")
    except Exception:
        if dataset_path.endswith(".json") or dataset_path.endswith(".jsonl"):
            dataset = load_dataset("json", data_files=dataset_path, split="train")
        elif dataset_path.endswith(".csv"):
            dataset = load_dataset("csv", data_files=dataset_path, split="train")
        else:
            dataset = load_dataset(dataset_path, split="train")

    # --------------- Normalise every dataset into a "text" column ---------------
    # This avoids formatting_func compatibility issues across TRL/Unsloth versions.
    columns = set(dataset.column_names)

    if "text" in columns:
        print(f"Dataset format: plain text ({len(dataset)} rows)")
    elif "messages" in columns or "conversations" in columns:
        msg_col = "messages" if "messages" in columns else "conversations"
        print(f"Dataset format: conversational / {msg_col} ({len(dataset)} rows)")

        # Ensure tokenizer has a chat template (instruct models always do)
        if tokenizer.chat_template is None:
            tokenizer.chat_template = (
                "{% for message in messages %}"
                "{{ '<|' + message['role'] + '|>\\n' + message['content'] + '\\n' }}"
                "{% endfor %}"
            )

        def _map_chat(example):
            convo = example[msg_col]
            # Ensure each message has "role" and "content" keys
            normalised = []
            for msg in convo:
                role = msg.get("role") or msg.get("from", "user")
                content = msg.get("content") or msg.get("value", "")
                # Map common aliases: "human"→"user", "gpt"/"bot"→"assistant"
                if role in ("human",):
                    role = "user"
                elif role in ("gpt", "bot"):
                    role = "assistant"
                normalised.append({"role": role, "content": content})
            example["text"] = tokenizer.apply_chat_template(
                normalised, tokenize=False, add_generation_prompt=False
            )
            return example

        dataset = dataset.map(_map_chat, remove_columns=[msg_col])
    elif "instruction" in columns:
        print(f"Dataset format: Alpaca-style ({len(dataset)} rows)")

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
        dataset = dataset.map(_map_alpaca, remove_columns=cols_to_remove)
    else:
        # Fallback: rename first column to "text"
        first_col = dataset.column_names[0]
        print(f"Dataset format: fallback to column '{first_col}' ({len(dataset)} rows)")
        dataset = dataset.rename_column(first_col, "text")

    print(f"Training on {len(dataset)} examples. Columns: {dataset.column_names}")

    max_steps = hyperparams.get("max_steps", 60)
    learning_rate = hyperparams.get("learning_rate", 2e-4)
    batch_size = hyperparams.get("batch_size", 2)
    epochs = hyperparams.get("epochs", None)

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
    }

    if epochs is not None:
        sft_config_kwargs["num_train_epochs"] = epochs
    else:
        sft_config_kwargs["max_steps"] = max_steps

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        max_seq_length=2048,
        args=SFTConfig(**sft_config_kwargs),
        callbacks=[MetricsCallback(job_id)],
    )

    trainer.train()

    output_model_path = f"/data/models/{job_id}"
    model.save_pretrained_merged(output_model_path, tokenizer, save_method="merged_16bit")

    metrics_dict = modal.Dict.from_name("agentforge-metrics")
    metrics_dict[job_id] = {
        "loss": 0.0,
        "epoch": epochs,
        "step": max_steps,
        "status": "completed",
        "model_output_path": output_model_path,
    }

    print(f"Training completed for job {job_id}. Model saved to {output_model_path}")
    return output_model_path
