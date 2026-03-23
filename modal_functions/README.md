# Modal functions (Phase 07)

**Canonical implementation:** `backend/modal_functions/` (imported by the API as `modal_functions.train`). This root folder keeps a short README only; `train.py` here is a legacy stub.

## Layout (target)

- `backend/modal_functions/train.py` — `@app.function(gpu="A10G", ...)` Unsloth QLoRA; metrics in `modal.Dict` `agentforge-metrics`.
- `backend/modal_functions/inference.py` — stub inference app for later deploy.

## Local dev

Without Modal credentials, set `MODAL_ENABLED=false` (default): jobs stay **pending**. Set `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` and `MODAL_ENABLED=true` to spawn GPU jobs.

## Wiring checklist

1. From repo root: `cd backend && modal deploy modal_functions/train.py`
2. Map `modal_job_id` + metrics back into `finetune_jobs` from Modal webhooks or polling.
3. Replace `FinetuneService.deploy_stub` with a call to Modal’s deployment API.
