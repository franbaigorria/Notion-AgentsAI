# Runbook: Railway Multi-Tenant Deploy

End-to-end procedure for deploying the voice-agent multi-tenant stack to
Railway, seeding a test tenant, and dispatching the agent against it with
`scripts/test_client.py`. Target: a new operator completes the full flow in
under 30 minutes.

---

## Prerequisites

Accounts:
- **Railway** — https://railway.com
- **LiveKit Cloud** — https://livekit.io (create a project, grab URL + API key + secret)

API keys for the test tenant providers (baseline: Nanci / clinica vertical):
- **Deepgram** (STT) — https://deepgram.com
- **Anthropic Claude** (LLM) — https://console.anthropic.com
- **ElevenLabs** (TTS) — https://elevenlabs.io

Local tooling:
- `railway` CLI — `npm i -g @railway/cli`
- `uv` — https://docs.astral.sh/uv/

---

## Step 1: Create the Railway project

```bash
railway login
railway init                     # creates a new project
railway link                     # link current dir to the new project
```

---

## Step 2: Provision Postgres

In the Railway dashboard (or via CLI), add the **PostgreSQL** plugin. Railway
injects `DATABASE_URL` with the driver-less scheme `postgresql://…`. The engine
auto-rewrites to `postgresql+asyncpg://…` at boot — no manual override needed.

Reference it from the worker service env via Railway's variable binding:

```
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

---

## Step 3: Set project secrets

Generate the master key locally:

```bash
uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Set all secrets in Railway (UI → Variables, or CLI):

```bash
railway variables --set VAULT_MASTER_KEY="<generated Fernet key>"
railway variables --set USE_TENANT_REGISTRY=true
railway variables --set LIVEKIT_URL="wss://<project>.livekit.cloud"
railway variables --set LIVEKIT_API_KEY="<api key>"
railway variables --set LIVEKIT_API_SECRET="<api secret>"
```

Provider keys (these go into the vault per-tenant in Step 5, NOT as worker env
vars — the agent reads them lazily via `TenantContext.get_secret`).

---

## Step 4: Deploy

```bash
railway up
```

What happens:
1. Railway builds the image from `Dockerfile`.
2. `railway.json` → `deploy.preDeployCommand` runs `uv run alembic upgrade head`
   on the new release before the container starts serving.
3. The worker boots via `CMD ["uv", "run", "python", "-m", "apps.launcher", "start"]`
   and connects outbound to LiveKit Cloud.

Verify:

```bash
railway logs                     # should show "DATABASE_URL scheme rewritten to postgresql+asyncpg://"
                                 # (if Railway injected postgresql://) and the agent worker lifecycle
```

---

## Step 5: Seed the test tenant

Run `scripts/seed_tenant.py` against the Railway Postgres instance. The
`railway run` prefix injects the remote `DATABASE_URL` and `VAULT_MASTER_KEY`
into your local shell:

```bash
# Shell-history mitigation: prefix with a space if HISTCONTROL=ignorespace,
# or run `history -d <linenum>` afterwards — the --secret values land in history.

 railway run uv run python scripts/seed_tenant.py \
   --name "Clinica Demo" \
   --vertical clinica \
   --secret deepgram=<DEEPGRAM_KEY> \
   --secret claude=<ANTHROPIC_KEY> \
   --secret elevenlabs=<ELEVENLABS_KEY>
```

Output prints the newly-created `tenant_id`. Save it — you pass it to
`test_client.py` in Step 6.

Idempotent re-run (rotate a key or update tenant metadata):

```bash
 railway run uv run python scripts/seed_tenant.py \
   --name "Clinica Demo v2" \
   --vertical clinica \
   --tenant-id <UUID from first run> \
   --secret deepgram=<rotated key>
```

---

## Step 6: Dispatch the agent + join as operator

Use `scripts/test_client.py` LOCALLY (it talks to LiveKit Cloud, not Railway):

```bash
export LIVEKIT_URL="wss://<project>.livekit.cloud"
export LIVEKIT_API_KEY="<api key>"
export LIVEKIT_API_SECRET="<api secret>"

uv run python scripts/test_client.py --tenant-id <UUID from Step 5>
```

Output:
- Dispatch ID + agent participant identity
- A LiveKit Agents Playground URL with a pre-signed token

Open the URL in a browser → join the room → talk to the agent. Verify the
voice loop works end-to-end.

---

## Rollback

### Fast rollback — keep code, disable multi-tenant

In Railway UI → Variables, set:

```
USE_TENANT_REGISTRY=false
```

The worker restarts and reverts to the YAML-vertical path. The tenants /
secrets rows in Postgres are untouched — no migration needed.

### Full rollback — revert to previous deploy

In Railway UI → Deployments → pick the last known-good deploy → "Redeploy".
Migrations are NOT automatically downgraded; if the bad deploy shipped a
schema change that broke things, run locally:

```bash
 railway run uv run alembic downgrade -1
```

---

## Add another tenant post-deploy

```bash
 railway run uv run python scripts/seed_tenant.py \
   --name "Clinica Two" \
   --vertical clinica \
   --secret deepgram=... \
   --secret claude=... \
   --secret elevenlabs=...
```

Then dispatch with the new tenant id:

```bash
uv run python scripts/test_client.py --tenant-id <new UUID>
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Worker crashes at boot with `MasterKeyMissingError` | `VAULT_MASTER_KEY` not set | Set the secret in Railway → redeploy |
| Migrations fail in preDeploy | Postgres plugin not linked, or DATABASE_URL malformed | Confirm `${{Postgres.DATABASE_URL}}` binding |
| `test_client.py` times out waiting for agent | `LIVEKIT_API_KEY`/`SECRET` mismatch between dispatch and worker | Ensure both use the SAME LiveKit project |
| Agent joins but crashes on first utterance | Tenant missing a provider secret | Re-run `seed_tenant.py` with all 3 `--secret` flags |
| `TenantNotFound` in worker logs | Wrong tenant UUID in dispatch metadata | Re-check UUID from Step 5 output |

---

## Self-hosted LiveKit (alternative)

If running LiveKit server yourself (not LiveKit Cloud), swap only `LIVEKIT_URL`
(e.g. `wss://livekit.example.com`). `test_client.py` and the worker are
url-agnostic — they talk to whatever URL is configured.

---

## Out of scope (deferred to future changes)

- RAG / knowledge ingestion — next change (`knowledge-rag-pipeline`)
- Admin UI for tenant management
- CI/CD pipeline (GitHub Actions → Railway)
- Autoscaling / multi-worker
- SIP / Twilio telephony — pipeline-only MVP uses LiveKit WebRTC
- Multi-environment (staging + prod) — single Railway project for test
