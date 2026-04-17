# Runbook: Master Key Rotation (VAULT_MASTER_KEY)

## Overview

The `VAULT_MASTER_KEY` is a Fernet symmetric key that encrypts every row in
`tenant_secrets`. Rotating it means re-encrypting all existing ciphertexts with
the new key before swapping the environment variable.

---

## WARNING — All-or-Nothing Semantics

**Partial rotation is corruption.**

If you swap `VAULT_MASTER_KEY` before all rows are re-encrypted, any row that
still holds ciphertext from the OLD key will raise `VaultDecryptError` when the
vault tries to decrypt it with the NEW key. There is no automatic fallback.

The helper script (`scripts/rotate_master_key.py`) runs the entire re-encryption
inside a **single database transaction**. If any row fails, the transaction is
rolled back and the database is left unchanged. The environment variable is
**not** updated until you verify the script exited successfully.

---

## Prerequisites

- Access to the Railway project (or wherever `VAULT_MASTER_KEY` is set)
- `pg_dump` installed and pointing at the production database
- Python environment with `cryptography` installed (`uv run python ...`)
- `DATABASE_URL` pointing at the target database

---

## Step-by-Step Procedure

### Step 1 — Generate the new Fernet key

```bash
uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Save the output. Call it `NEW_KEY`. Do **not** discard the current `VAULT_MASTER_KEY`
(call it `OLD_KEY`) until rotation is complete and verified.

### Step 2 — Back up the database

```bash
pg_dump "$DATABASE_URL" > backup_before_rotation_$(date +%Y%m%d_%H%M%S).sql
```

Store this backup somewhere safe. If rotation fails catastrophically, this is
your recovery path.

### Step 3 — Run the rotation script

```bash
OLD_KEY="<old key here>" \
NEW_KEY="<new key here>" \
DATABASE_URL="$DATABASE_URL" \
uv run python scripts/rotate_master_key.py
```

The script will:
1. Connect to the database using `DATABASE_URL`
2. Load `OLD_KEY` and `NEW_KEY` from environment variables
3. Open a single transaction
4. Fetch every row from `tenant_secrets`
5. Decrypt each ciphertext with `OLD_KEY`
6. Re-encrypt with `NEW_KEY`
7. Update the row in-place (`rotated_at = now()`)
8. Commit — or roll back on any error

On success you will see:

```
Rotated N secrets across M tenants. Transaction committed. Safe to update VAULT_MASTER_KEY.
```

On failure you will see:

```
ERROR rotating secret <key_name> for tenant <tenant_id>: <reason>
Transaction rolled back. Database unchanged. Do NOT update VAULT_MASTER_KEY.
```

### Step 4 — Update the environment variable on Railway

1. Go to Railway → your service → Variables
2. Set `VAULT_MASTER_KEY` to `NEW_KEY`
3. Deploy / restart the service

### Step 5 — Verify decryption with the new key

After the service restarts, confirm at least one `vault.get()` call succeeds
without `VaultDecryptError`. The integration test suite is the fastest way:

```bash
DATABASE_URL="<prod-or-staging-url>" \
VAULT_MASTER_KEY="<new key>" \
uv run pytest tests/integration/core/test_fernet_postgres_vault.py -v
```

All tests must pass. If any test raises `VaultDecryptError`, rotation was
incomplete — restore the backup from Step 2 and investigate.

### Step 6 — Discard the old key

Once Step 5 is confirmed green, the old key can be discarded. Do not store it
anywhere accessible.

---

## Rollback Procedure

If you need to revert **before** swapping the env var (i.e. the script failed):

- Nothing to do. The transaction was rolled back. The database is unchanged.
- Fix the issue (wrong `OLD_KEY`, unreachable DB, etc.) and re-run the script.

If you need to revert **after** swapping the env var (script succeeded but
service is behaving unexpectedly):

1. Restore the database from the `pg_dump` backup (Step 2).
2. Set `VAULT_MASTER_KEY` back to `OLD_KEY` on Railway.
3. Restart the service.
4. Investigate what went wrong before attempting rotation again.

---

## Helper Script

The rotation script lives at `scripts/rotate_master_key.py`.
Run it with both `OLD_KEY` and `NEW_KEY` as env vars — it does **not** read from
`VAULT_MASTER_KEY` directly to prevent accidental self-corruption.
