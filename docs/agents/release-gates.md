# Release gates for agents

Use automated checks before promoting an agent version to production.

## Security score floor

Run a red-team campaign and fail the pipeline if `overall_score` is below your threshold (for example 50). The workflow [`.github/workflows/redteam.yml`](../../.github/workflows/redteam.yml) demonstrates this pattern.

## Regression between runs

Run two campaigns on the same agent (or on consecutive versions) and assert the second `overall_score` is not materially lower than the first. Mock mode returns stable scores; with Promptfoo, allow a small delta for flakiness.

## Version diff (CI)

Call:

`GET /api/v1/agents/{agent_id}/versions/diff?from={N}&to={M}`

with a Bearer token. Fail if unexpected graph or `execution_policy` changes appear for a release branch.

## Scorecard (dashboards / CI)

`GET /api/v1/agents/{agent_id}/scorecard` returns:

- `versions` — snapshot history
- `executions_by_agent_version` — counts and average duration per `agent_version_number` captured at execution start
- `recent_campaigns` — latest security assessments

Use this JSON in dashboards or to block deploy when failure rates spike for the latest version.

## Production sandbox

Set `ENVIRONMENT=production` and `SANDBOX_MODE=docker` so skill code never runs in the unprivileged subprocess sandbox.
