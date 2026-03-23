import modal

app = modal.App("agentforge-finetune")
metrics_dict = modal.Dict.from_name("agentforge-metrics", create_if_missing=True)
data_volume = modal.Volume.from_name("agentforge-datasets", create_if_missing=True)

image = modal.Image.debian_slim().pip_install(
    "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git",
    "trl",
    "transformers",
    "datasets",
    "accelerate",
    "peft",
    "bitsandbytes",
    "torch",
)


@app.function(image=image, gpu="A10G", timeout=3600, volumes={"/data": data_volume})
def train_model(job_id: str, base_model: str, dataset_path: str, hyperparams: dict):
    import modal
    from datasets import load_dataset
    from transformers import TrainerCallback
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel, is_bfloat16_supported

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
    }

    if epochs is not None:
        sft_config_kwargs["num_train_epochs"] = epochs
    else:
        sft_config_kwargs["max_steps"] = max_steps

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
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
