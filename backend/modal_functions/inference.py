"""
AgentForge — Modal inference endpoint for fine-tuned models.

Deploy: `cd backend && modal deploy modal_functions/inference.py`

After deploy, Modal prints the web endpoint URL. Set it in .env:
  MODAL_INFERENCE_URL=https://<workspace>--agentforge-inference-generate.modal.run
"""

import modal

app = modal.App("agentforge-inference")
data_volume = modal.Volume.from_name("agentforge-datasets", create_if_missing=True)

image = (
    modal.Image.debian_slim()
    .apt_install("git")
    .pip_install(
        "fastapi[standard]",
        "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git",
        "transformers",
        "torch",
    )
)

# Cache loaded models across warm invocations (keyed by job_id)
_model_cache: dict = {}


@app.function(
    image=image,
    gpu="A10G",
    timeout=300,
    volumes={"/data": data_volume},
    # min_containers=1 keeps a GPU warm 24/7 (~$1.10/h) — too expensive for Starter plan.
    # Requests will cold-start in ~30-60s instead.
)
@modal.fastapi_endpoint(method="POST")
def generate(request: dict) -> dict:
    """
    Generate text from a fine-tuned model stored on Modal Volume.

    Body: {
        "job_id": "uuid",
        "prompt": "User: hello\nAssistant:",
        "max_new_tokens": 128,   # optional, default 128
        "temperature": 0.7       # optional, default 0.7
    }
    """
    from unsloth import FastLanguageModel

    job_id: str | None = request.get("job_id")
    prompt: str = request.get("prompt", "")
    max_new_tokens: int = int(request.get("max_new_tokens", 128))
    temperature: float = float(request.get("temperature", 0.7))

    if not job_id:
        return {"error": "job_id is required", "status": 400}

    if not prompt:
        return {"error": "prompt is required", "status": 400}

    model_path = f"/data/models/{job_id}"

    # Load model (cached per job_id within the same container)
    if job_id not in _model_cache:
        import os

        if not os.path.exists(model_path):
            return {
                "error": f"Model for job {job_id} not found. "
                "Ensure training completed and model was saved.",
                "status": 404,
            }
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_path,
            max_seq_length=2048,
            load_in_4bit=True,
        )
        FastLanguageModel.for_inference(model)
        _model_cache[job_id] = (model, tokenizer)

    model, tokenizer = _model_cache[job_id]

    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        do_sample=temperature > 0,
    )
    # Decode only the newly generated tokens (skip the prompt)
    generated = outputs[0][inputs["input_ids"].shape[1] :]
    response_text = tokenizer.decode(generated, skip_special_tokens=True)

    return {"response": response_text, "job_id": job_id, "status": 200}
