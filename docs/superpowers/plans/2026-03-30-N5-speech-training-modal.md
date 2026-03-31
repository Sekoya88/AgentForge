# Phase N5 — Speech training custom (Modal)

> **Statut : implémenté (MVP)** — flux LLM inchangé ; speech : API + stubs Modal + UI onglets + résolution `job_id` + datasets voice / examples + opt-in feedback.

**Spec :** `docs/superpowers/specs/2026-03-30-agentforge-roadmap-design.md` § Phase N5.

## Déjà en place

- **Résolution runtime `finetune_job_id` → `endpoint_url`** : `AgentService._enrich_finetuned_speech_graph` (ASR `whisper`, TTS `tts_voice`), exécution + background + resume.
- **Providers** `finetuned_whisper` / `finetuned_tts` (HTTP), SDK, builder.
- **`GET /api/v1/speech/deployed`** — jobs `whisper` / `tts_voice` complétés avec `inference_endpoint`.
- **Tables** `speech_examples`, `voice_samples` (migration `015_speech_data`) ; **`POST/GET /api/v1/speech/voice-samples`**.
- **Opt-in collecte** : `users.collect_speech_examples`, `agents.collect_speech_examples`, persistance `executions.input_audio_b64` (multipart `/execute/audio`), hook sur feedback ≥ 0.8 + graphe avec nœud `asr`. **`PATCH /api/v1/auth/me`** (`collect_speech_examples`).
- **`POST /api/v1/finetune`** accepte **`text_sft` | `whisper` | `tts_voice`**. Sans Modal : jobs speech en **`pending`**. Avec Modal : spawn **`agentforge-speech` → `train_speech_model`** (stub rapide qui écrit `inference_endpoint` dans le Dict partagé).
- **Fichier Modal** : `backend/modal_functions/train_speech.py` — `modal deploy backend/modal_functions/train_speech.py`.
- **`deploy()`** : ne remplace pas un `inference_endpoint` déjà renseigné ; stubs locaux par modalité (`…/speech/whisper/{id}`, `…/speech/tts/{id}`).
- **Frontend** : `/finetune` — onglets **All / LLM / Speech** ; `/finetune/new` — type de job LLM vs Whisper vs TTS ; **builder** — listes déroulantes « deployed job » pour ASR/TTS fine-tunés.
- **Tests** : `test_finetune` (modalités speech pending), `test_modal_speech_smoke` (skip sauf `MODAL_SPEECH_SMOKE=1`).

---

## 1. Données & collecte

- [x] Table `speech_examples` + `voice_samples`.
- [x] Hook post-feedback (opt-in user ou agent, score ≥ 0.8, nœud `asr`, audio d’entrée persisté).
- [x] `POST` / `GET` voice-samples.

---

## 2. Modal — entraînement

- [x] Stub `train_speech_model` (Whisper / TTS) — **remplacer** par entraînement HF réel (Whisper fine-tune, XTTS / pipeline voix).
- [ ] Secrets HF / quotas documentés pour la recette prod.

---

## 3. Backend

- [x] `POST /finetune` avec `whisper` | `tts_voice`.
- [x] `GET /speech/deployed`.
- [x] Enrichissement graphe `job_id` → URL.
- [x] `AgentService` injecte `speech_example_repo` + `user_repo` (DI).

---

## 4. Frontend

- [x] `/finetune` — filtre Speech / LLM.
- [x] `/finetune/new` — création job speech.
- [x] Builder — sélection job déployé (Whisper / TTS).

---

## 5. SDK Python

- [x] Builder `job_id` / `endpoint_url` / `voice_id` (inchangé).

---

## 6. Tests

- [x] Tests API finetune modalités speech (pending hors Modal).
- [x] Marqueur optionnel `MODAL_SPEECH_SMOKE=1`.

---

## Critères d'acceptation produit

- [x] Contournement : URL d’inférence ou job complété + `job_id` sans URL manuelle (résolution serveur).
- [ ] Job Whisper **réel** Modal → ASR end-to-end sans URL collée (bloqué sur training HF complet).
- [ ] Job TTS **réel** → synthèse end-to-end depuis UI (idem).
