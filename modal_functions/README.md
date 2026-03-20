# Modal functions (Phase 07)

Placeholder for **Unsloth QLoRA** training and inference on [Modal](https://modal.com).

## Layout (target)

- `train.py` — `@app.function(gpu="A10G", ...)` wrapping Unsloth SFT/QLoRA; reads `dataset_path` + `hyperparams` from `finetune_jobs`.
- `inference.py` — deployable endpoint for fine-tuned weights.

## Local dev

Without Modal credentials, the API keeps jobs in `pending` and `POST /api/v1/finetune/{id}/deploy` returns a **stub** URL. Set `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` in `.env` when wiring real functions.

## Wiring checklist

1. `modal deploy modal_functions/train.py`
2. Map `modal_job_id` + metrics back into `finetune_jobs` from Modal webhooks or polling.
3. Replace `FinetuneService.deploy_stub` with a call to Modal’s deployment API.
