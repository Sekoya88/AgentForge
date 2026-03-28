# Streaming Modal Inference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add token-streaming from Modal inference endpoint to the finetune detail page evaluate section, so users see tokens as they arrive instead of waiting 30s for a full response.

**Architecture:** Add a `generate_stream` ASGI app to `modal_functions/inference.py` using `@modal.asgi_app()` (Modal's supported pattern for streaming). The backend proxies this as an SSE stream via a new `POST /api/v1/finetune/{job_id}/inference-stream` endpoint. The frontend `EvaluateSection` component calls this endpoint with `fetch()` + `localStorage.getItem("access_token")` and appends tokens in real-time. The agent execution path (`_invoke_finetuned`) stays synchronous — LangGraph needs a complete response.

**Tech Stack:** Modal `@modal.asgi_app()`, FastAPI `StreamingResponse`, `transformers.TextIteratorStreamer`, httpx async streaming, `localStorage.getItem("access_token")`

---

### Task 1: Streaming Modal endpoint

**Files:**
- Modify: `backend/modal_functions/inference.py`

The key constraint: `@modal.fastapi_endpoint` does not reliably support streaming responses. Use `@modal.asgi_app()` with an embedded FastAPI app instead — Modal's documented pattern for SSE/streaming.

- [ ] **Step 1: Add `generate_stream` ASGI app at the bottom of `inference.py`**

Add after the existing `evaluate` function:

```python
# ── Streaming endpoint (separate ASGI app — Modal supports StreamingResponse here) ──

def _build_stream_app():
    """Build a FastAPI ASGI app for streaming inference."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    import json

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
            from unsloth import FastLanguageModel
            from transformers import TextIteratorStreamer
            from threading import Thread
            import os

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
            streamer = TextIteratorStreamer(
                tokenizer, skip_prompt=True, skip_special_tokens=True
            )
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
```

- [ ] **Step 2: Redeploy inference**

```bash
cd backend && modal deploy modal_functions/inference.py
```

Expected: Modal prints two new routes — `generate-stream` alongside the existing `generate` and `evaluate`.

- [ ] **Step 3: Smoke test streaming endpoint**

```bash
# Replace URL with your Modal generate-stream endpoint
curl -N -X POST https://<workspace>--agentforge-inference-generate-stream.modal.run/ \
  -H "Content-Type: application/json" \
  -d '{"job_id": "YOUR_JOB_ID", "prompt": "Hello", "max_new_tokens": 20, "temperature": 0.7}'
```

Expected: SSE lines like `data: {"token": " world"}` streaming, ending with `data: [DONE]`.

- [ ] **Step 4: Commit**

```bash
git add backend/modal_functions/inference.py
git commit -m "feat(inference): add streaming token endpoint via Modal asgi_app"
```

---

### Task 2: Backend SSE proxy endpoint

**Files:**
- Modify: `backend/app/api/v1/finetune.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/api/test_finetune_inference_stream.py`:

```python
# backend/tests/api/test_finetune_inference_stream.py
import pytest
from httpx import AsyncClient


# Helper: register + login to get auth headers
async def get_auth_headers(client: AsyncClient) -> dict:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "stream@test.com", "password": "testpass123", "name": "Stream"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "stream@test.com", "password": "testpass123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_inference_stream_missing_prompt(client: AsyncClient, alembic_ready):
    headers = await get_auth_headers(client)
    resp = await client.post(
        "/api/v1/finetune/fake-job-id/inference-stream",
        headers=headers,
        json={},  # missing prompt
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_inference_stream_no_modal_url(client: AsyncClient, alembic_ready):
    headers = await get_auth_headers(client)
    # MODAL_INFERENCE_URL is not set in test env → should 503
    resp = await client.post(
        "/api/v1/finetune/fake-job-id/inference-stream",
        headers=headers,
        json={"prompt": "hello"},
    )
    assert resp.status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/api/test_finetune_inference_stream.py -v
```

Expected: `ModuleNotFoundError` or 404 (endpoint doesn't exist yet).

- [ ] **Step 3: Add imports and Pydantic schema to `finetune.py`**

At the top of `backend/app/api/v1/finetune.py`, add alongside existing imports:

```python
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import httpx
```

After the existing imports block, add:

```python
class InferenceStreamRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 128
    temperature: float = 0.7
```

- [ ] **Step 4: Add the stream endpoint to `finetune.py`**

Add before the final `router` line (or at the end of the router definition):

```python
@router.post("/{job_id}/inference-stream")
async def inference_stream(
    job_id: str,
    body: InferenceStreamRequest,
    current_user: User = Depends(get_current_user),
    settings: Annotated[Settings, Depends(get_settings_dep)] = ...,
):
    """Proxy streaming tokens from Modal inference endpoint."""
    from app.config import Settings
    from app.dependencies import get_settings_dep

    modal_url = settings.modal_inference_url
    if not modal_url:
        raise HTTPException(status_code=503, detail="Modal inference not configured")

    # Modal asgi_app generates a separate URL: replace /generate with /generate-stream
    stream_url = modal_url.replace("/generate", "/generate-stream/")

    payload = {
        "job_id": job_id,
        "prompt": body.prompt,
        "max_new_tokens": body.max_new_tokens,
        "temperature": body.temperature,
    }

    async def _proxy():
        async with httpx.AsyncClient(timeout=120.0) as http:
            async with http.stream("POST", stream_url, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        yield line + "\n\n"

    return StreamingResponse(
        _proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

Note: `get_settings_dep` and `Settings` must be imported. Add them to the existing import from `app.dependencies`:

```python
from app.dependencies import get_current_user, get_finetune_service, get_redis_optional, get_settings_dep
from app.config import Settings
```

And add `Settings` and `Annotated` to the top-level imports (both are likely already present in the file via other routes — check before adding).

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/api/test_finetune_inference_stream.py -v
```

Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/finetune.py backend/tests/api/test_finetune_inference_stream.py
git commit -m "feat(api): add /inference-stream SSE proxy for finetune evaluate"
```

---

### Task 3: Frontend streaming evaluate UI

**Files:**
- Modify: `frontend/src/app/finetune/[id]/page.tsx` (the `EvaluateSection` component, lines 118–200)

The `EvaluateSection` component receives `{ jobId, endpoint }` as props. Auth token is read from `localStorage.getItem("access_token")` (same as `authHeaders()` in `@/lib/api.ts`).

- [ ] **Step 1: Add streaming state and refs to `EvaluateSection`**

After the existing `useState` declarations at the top of `EvaluateSection` (line ~119), add:

```typescript
const [streamingResponse, setStreamingResponse] = useState<string>("");
const [isStreaming, setIsStreaming] = useState(false);
const streamAbortRef = useRef<AbortController | null>(null);
```

- [ ] **Step 2: Add `handleStreamEvaluate` function inside `EvaluateSection`**

Add after the existing `runEval` function (line ~143):

```typescript
async function handleStreamEvaluate() {
  const prompt = prompts.trim();
  if (!prompt) return;
  if (streamAbortRef.current) streamAbortRef.current.abort();
  const ctrl = new AbortController();
  streamAbortRef.current = ctrl;
  setStreamingResponse("");
  setIsStreaming(true);

  const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  try {
    const resp = await fetch(
      `${BASE}/api/v1/finetune/${jobId}/inference-stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ prompt, max_new_tokens: 128, temperature: 0.7 }),
        signal: ctrl.signal,
      }
    );

    if (!resp.ok) {
      setStreamingResponse(`Error: ${resp.status} ${resp.statusText}`);
      return;
    }

    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let done = false;

    while (!done) {
      const { done: streamDone, value } = await reader.read();
      done = streamDone;
      if (value) {
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") { done = true; break; }
          try {
            const { token: tok, error } = JSON.parse(raw);
            if (error) { setStreamingResponse(`Error: ${error}`); done = true; break; }
            if (tok) setStreamingResponse((prev) => prev + tok);
          } catch {}
        }
      }
    }
  } catch (e: unknown) {
    if (e instanceof Error && e.name !== "AbortError") {
      setStreamingResponse(`Error: ${e.message}`);
    }
  } finally {
    setIsStreaming(false);
  }
}
```

- [ ] **Step 3: Add cleanup on unmount**

Add a `useEffect` at the top of `EvaluateSection` (after the `useRef` declaration):

```typescript
useEffect(() => {
  return () => { streamAbortRef.current?.abort(); };
}, []);
```

- [ ] **Step 4: Add streaming UI after the existing "Run evaluation" button**

Find the `<button>` with `onClick={runEval}` (line ~165). Add a second button and the output box right after it:

```tsx
<button
  type="button"
  onClick={handleStreamEvaluate}
  disabled={isStreaming || !prompts.trim()}
  className="af-btn-secondary ml-2 mb-4 flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
>
  {isStreaming ? (
    <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
  ) : (
    <span className="material-symbols-outlined text-sm">stream</span>
  )}
  {isStreaming ? "Streaming…" : "Stream (live)"}
</button>

{(isStreaming || streamingResponse) && (
  <div className="mb-4 rounded-lg border border-af-border/30 bg-af-surface-low p-4">
    <p className="mb-2 text-[10px] uppercase tracking-wider text-af-muted-dim">
      {isStreaming ? "Generating…" : "Streamed response"}
    </p>
    <pre className="whitespace-pre-wrap font-mono text-xs text-af-on-surface">
      {streamingResponse}
      {isStreaming && <span className="animate-pulse text-af-tertiary">▋</span>}
    </pre>
  </div>
)}
```

- [ ] **Step 5: Verify locally**

```bash
cd frontend && npm run dev
# Open /finetune/<job_id> for a deployed job, enter a prompt, click "Stream (live)"
```

Expected: tokens appear progressively, cursor blinks while generating.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/finetune/
git commit -m "feat(ui): stream inference tokens live in finetune evaluate section"
```
