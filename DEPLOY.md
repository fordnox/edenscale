# Deployment (Kamal)

The backend is **built and pushed by GitHub Actions**, then **deployed by Kamal**.
On every push to `main` that touches `apps/backend/**` (or the Kamal config),
`.github/workflows/deploy.yml`:

1. Builds `./apps/backend/Dockerfile` and pushes `ghcr.io/fordnox/speed:<git-sha>`.
2. Runs `kamal deploy --skip-push --version=<git-sha>` — pulls that image onto the
   server and boots `web` + `worker` containers behind kamal-proxy (auto TLS).
3. Runs `alembic upgrade head` inside the new image.

Redis run as Kamal **accessories** on the same host.
Postgres is https://neon.com/ database.

## One-time setup

### 1. Provision a server
Any Ubuntu host with SSH access. Kamal installs Docker for you on first deploy.
Point a DNS A-record (e.g. `api.gtlane.net`) at the server's IP.

### 2. Fill in `config/deploy.yml`
Replace every `YOUR_SERVER_IP` and set `proxy.host` / `APP_DOMAIN` to your domain.

### 3. Store secrets in 1Password
All deploy-time secrets live in a single 1Password item, `op://CI/gtlane`,
with these fields (referenced by `.kamal/secrets`):

| Field | Value |
| --- | --- |
| `KAMAL_REGISTRY_PASSWORD` | GitHub PAT with `read:packages` (servers use it to pull from ghcr) |
| `APP_DATABASE_DSN` | `postgresql+psycopg2://app:STRONGPASS@gtlane-db:5432/app` |
| `OPENROUTER_API_KEY` | your key |
| `HANKO_API_URL` | `https://<tenant>.hanko.io` |
| `SSH_PRIVATE_KEY` | Private key whose public half is in the server's `~/.ssh/authorized_keys` |

The **only** GitHub Actions secret you need is `OP_SERVICE_ACCOUNT_TOKEN` — a
1Password [service account](https://developer.1password.com/docs/service-accounts/)
token that grants read access to the `CI` vault. The workflow installs the `op`
CLI and Kamal's `.kamal/secrets` fetches the rest at deploy time.

To run Kamal locally, install the `op` CLI and `op signin` (or export
`OP_SERVICE_ACCOUNT_TOKEN`) — no other env vars needed.

### 4. First deploy
From the workflow (push to `main` or run it manually via **workflow_dispatch**),
or locally if you have `kamal` + SSH access:

```bash
# Export the same secrets locally, then:
kamal setup            # provisions Docker, boots accessories + app (builds locally)
```

## Day-to-day (local CLI)

```bash
gem install kamal -v "~> 2.0"

kamal deploy                                   # build + push + deploy
kamal app logs -f                              # tail app logs
kamal app exec --reuse "/app/.venv/bin/alembic upgrade head"   # run migrations
kamal accessory boot redis                     # (re)start an accessory
kamal rollback <previous-sha>                  # roll back
kamal proxy logs                               # TLS / routing logs
```

Secrets locally are read from `.kamal/secrets`, which only references env vars —
export them (or use a dotenv loader) before running `kamal`.
