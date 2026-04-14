# Sandbox runtime (production)

## Modes

| `SANDBOX_MODE` | Use case | Isolation |
|----------------|----------|-----------|
| `subprocess` (default) | Local dev, CI without Docker | Child `python -c` with temp `cwd`, timeout only. **Not** a security boundary — no cgroups/seccomp in this codebase. |
| `docker` | Production / untrusted code | Ephemeral container: `--network none`, memory/CPU caps, read-only FS, non-root user (`docker_sandbox.py`). Requires Docker socket on the API host. |

## Recommendation

- **Development:** `SANDBOX_MODE=subprocess` (default in `.env.example`).
- **Production:** set **`SANDBOX_MODE=docker`** and mount the Docker socket into the backend container only if you run the API in Docker; lock down socket permissions and use a dedicated node pool if possible.

## Operational notes

- **Subprocess** runs each snippet in a fresh temp directory (`af-sandbox-*`) so relative paths do not leak across invocations.
- **Docker** failures surface as non-zero tool exits; monitor `docker` daemon health and image pulls (`python:3.12-slim`).
- For stricter isolation (seccomp, AppArmor, gVisor), extend `DockerSandboxRuntime` or route skills to an external runner — out of scope for this runbook.

## CI

Optional matrix job with `SANDBOX_MODE=docker` when the runner exposes Docker; otherwise skip — factory tests (`tests/test_sandbox_mode_factory.py`) validate mode wiring without executing code.

## GitHub Actions Deploy Secrets

Configure these in GitHub → Settings → Environments → production:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | VPS IP or hostname |
| `DEPLOY_USER` | SSH user (e.g. `deploy`) |
| `DEPLOY_SSH_KEY` | Private SSH key (the public key must be in `~/.ssh/authorized_keys` on the VPS) |
| `DEPLOY_PATH` | Absolute path to the repo on the VPS (e.g. `/home/deploy/agentforge`) |
