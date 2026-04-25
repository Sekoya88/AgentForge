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
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install("numpy>=2.2.0,<3")
    .pip_install(
        "fastapi[standard]",
        "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git",
        "transformers",
        "torch",
        "torchvision",
        "accelerate",
        "bitsandbytes",
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
            max_seq_length=8192,
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


@app.function(
    image=image,
    gpu="A10G",
    timeout=600,
    volumes={"/data": data_volume},
)
@modal.fastapi_endpoint(method="POST")
def evaluate(request: dict) -> dict:
    """
    Evaluate a fine-tuned model on a batch of prompts.

    Body: {
        "job_id": "uuid",
        "prompts": ["prompt1", "prompt2", ...],
        "max_new_tokens": 128,
        "temperature": 0.1
    }
    Returns: {"job_id": "...", "results": [...], "count": N}
    """
    import os
    import time

    from unsloth import FastLanguageModel

    job_id: str | None = request.get("job_id")
    prompts: list = request.get("prompts", [])
    max_new_tokens: int = int(request.get("max_new_tokens", 128))
    temperature: float = float(request.get("temperature", 0.1))

    if not job_id:
        return {"error": "job_id is required", "status": 400}
    if not prompts:
        return {"error": "prompts list is required", "status": 400}

    model_path = f"/data/models/{job_id}"

    if job_id not in _model_cache:
        if not os.path.exists(model_path):
            return {"error": f"Model for job {job_id} not found.", "status": 404}
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_path,
            max_seq_length=8192,
            load_in_4bit=True,
        )
        FastLanguageModel.for_inference(model)
        _model_cache[job_id] = (model, tokenizer)

    model, tokenizer = _model_cache[job_id]

    results = []
    for prompt in prompts[:20]:  # Cap at 20
        start = time.time()
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
        )
        generated = outputs[0][inputs["input_ids"].shape[1] :]
        response_text = tokenizer.decode(generated, skip_special_tokens=True)
        elapsed = time.time() - start
        results.append(
            {
                "prompt": prompt[:500],
                "response": response_text,
                "tokens": len(generated),
                "elapsed_seconds": round(elapsed, 2),
            }
        )

    return {"job_id": job_id, "results": results, "count": len(results), "status": 200}


# ── Streaming endpoint (separate ASGI app — Modal supports StreamingResponse here) ──


def _build_stream_app():
    """Build a FastAPI ASGI app for streaming inference."""
    import json

    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse

    _stream_app = FastAPI()
    _stream_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST"],
        allow_headers=["*"],
    )

    @_stream_app.post("/")
    async def generate_stream_handler(request: Request):
        body = await request.json()
        job_id: str | None = body.get("job_id")
        prompt: str = body.get("prompt", "")
        max_new_tokens: int = int(body.get("max_new_tokens", 128))
        temperature: float = float(body.get("temperature", 0.7))

        if not job_id or not prompt:

            def _err():
                yield f"data: {json.dumps({'error': 'job_id and prompt required'})}\n\n"

            return StreamingResponse(_err(), media_type="text/event-stream")

        def _stream():
            import os
            from threading import Thread

            from transformers import TextIteratorStreamer
            from unsloth import FastLanguageModel

            model_path = f"/data/models/{job_id}"
            if job_id not in _model_cache:
                if not os.path.exists(model_path):
                    yield f"data: {json.dumps({'error': f'Model {job_id} not found'})}\n\n"
                    return
                model, tokenizer = FastLanguageModel.from_pretrained(
                    model_name=model_path,
                    max_seq_length=8192,
                    load_in_4bit=True,
                )
                FastLanguageModel.for_inference(model)
                _model_cache[job_id] = (model, tokenizer)

            model, tokenizer = _model_cache[job_id]
            inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
            streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
            gen_kwargs = dict(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                streamer=streamer,
            )
            thread = Thread(target=model.generate, kwargs=gen_kwargs)
            thread.start()

            for token_text in streamer:
                yield f"data: {json.dumps({'token': token_text})}\n\n"

            yield "data: [DONE]\n\n"
            thread.join()

        return StreamingResponse(_stream(), media_type="text/event-stream")

    return _stream_app


@app.function(
    image=image,
    gpu="A10G",
    timeout=300,
    volumes={"/data": data_volume},
)
@modal.asgi_app()
def generate_stream():
    """Streaming inference endpoint — returns tokens via SSE."""
    return _build_stream_app()
