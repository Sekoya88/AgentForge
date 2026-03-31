# Superpowers — specs & plans (AgentForge)

Workflow (Cursor / Claude Code) : invoquer le skill **using-superpowers** en début de session ; pour du gros chantier, **brainstorming** puis **writing-plans** avant le code ; **verification-before-completion** avant de dire « c’est fini ».

## Contenu

| Chemin | Rôle |
|--------|------|
| `specs/2026-03-30-agentforge-roadmap-design.md` | Spec approuvée : tracks N1–N5 + Track C + **tableau d’état d’implémentation** (tenu à jour) |
| `plans/2026-03-30-N1-ollama-sdk-unit-tests.md` | N1 — **terminé** (checklist historique détaillée) |
| `plans/2026-03-30-N2-ollama-integration-tests.md` | N2 — **terminé** (`sdk/tests/integration/`, marker `integration`) |
| `plans/2026-03-30-N3-speech-asr-tts.md` | N3 — **terminé** (référence) |
| `plans/2026-03-30-N4-oauth-scheduling.md` | N4 — **terminé** (OAuth Google + `agent_schedules` + client + UI) |
| `plans/2026-03-30-N5-speech-training-modal.md` | N5 — **partiel** : HTTP `finetuned_*` + SDK + builder + `GET /speech/deployed` ; reste Modal / datasets / résolution `job_id` |
| `plans/2026-03-30-track-C-backlog.md` | Track C — index des vagues C1–C5 |

Les plans N1/N3 conservent des étapes `[ ]` comme archive d’exécution ; pour l’état actuel, se fier au **statut** en tête de chaque plan `2026-03-30-N*.md` et au tableau dans le spec.
