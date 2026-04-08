# Superpowers — specs & plans (AgentForge)

Workflow (Cursor / Claude Code) : invoquer le skill **using-superpowers** en début de session ; pour du gros chantier, **brainstorming** puis **writing-plans** avant le code ; **verification-before-completion** avant de dire « c'est fini ».

## Contenu actif

| Chemin | Rôle | Statut |
|--------|------|--------|
| `AGENTFORGE_ROADMAP.md` | Roadmap produit complète — use cases, état livré, 5 sprints | Référence principale |
| `plans/2026-04-01-agentforge-roadmap.md` | Plan d'exécution : fiabilité chat/API, polish frontend, tests | Task 1 ✅ — Tasks 2–11 en attente |
| `plans/2026-04-04-long-term-memory.md` | Plan détaillé : mémoire persistante agents (pgvector) | Pas démarré — Sprint 2 Task 2.1 |

## Specs et plans supprimés (livrés)

Les specs et plans suivants ont été supprimés car leurs features sont entièrement dans le codebase :

| Fichier supprimé | Raison |
|-----------------|--------|
| `specs/2026-03-30-agentforge-roadmap-design.md` | Tracks N1–N5 tous livrés (Ollama, speech, schedules, OAuth, SDK) |
| `specs/2026-04-04-agent-realtime-animations-design.md` | `AgentToastStack`, `AgentStepChips`, `AgentActivityIcon`, `InterruptPopup` livrés |
