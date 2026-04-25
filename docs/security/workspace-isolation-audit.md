# Workspace / tenant isolation audit

**Scope:** AgentForge backend (`backend/app`). **Method:** static review (grep + repository patterns). **RLS:** Postgres Row-Level Security is **not** enabled for workspace tables in this repo — isolation relies on **application-layer `user_id` (and workspace membership where implemented)** on every query path.

## Summary

| Surface | Enforcement | Verdict |
|---------|-------------|---------|
| Agents CRUD | `PostgresAgentRepository` filters `AgentModel.user_id` on get/list/update/delete | OK |
| Executions | `get_execution` / `list_executions` join `ExecutionModel.user_id` | OK |
| Agent versions | Version reads check parent `AgentModel.user_id` | OK |
| Schedules | `user_id` on schedule rows; tick skips `user_id is None` | OK |
| SSE streams | `stream_agent_execution` calls `svc.get_execution(..., user.id)` before subscribing | OK |
| Forge stream | `get_current_user` on route | OK (execution must belong to user via service layer elsewhere) |
| Knowledge / campaigns | Repositories accept `user_id` — verify each router passes `current_user.id` | **Spot-check** when adding endpoints |

## Gaps / follow-ups

1. **New endpoints:** Any raw `session.execute` without `user_id` in `WHERE` is a potential IDOR — require repo methods with explicit `user_id` or workspace membership.
2. **Workspace members:** `workspace_member` migration adds membership; ensure all multi-tenant reads use the membership-aware path (grep `workspace` when extending APIs).
3. **Future hardening:** Postgres RLS by `workspace_id` or `user_id` as a separate migration if regulatory posture requires DB-enforced isolation.

## Commands used

```bash
rg "user_id" backend/app/infrastructure/persistence/postgres/agent_repo.py
rg "get_current_user" backend/app/api/v1/
```

Re-run before releases if persistence or auth layers change materially.
