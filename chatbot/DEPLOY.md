# Deploying the RTA Smart Monitoring Assistant to Railway

Same flow as the Health-repo assistant. The repo already contains everything Railway
needs: `railway.toml` at the repo root points at `chatbot/Dockerfile`, which builds the
frontend, installs the backend, and bakes in the CSVs.

## Step 1 — Create the Railway service

1. Go to https://railway.app/dashboard → **New Project** → **Deploy from GitHub repo**
2. Select the `reports` repo
3. In the service settings, set the **branch** Railway should deploy (e.g. `main` once
   the chatbot branch is merged, or the feature branch directly)
4. Railway reads `railway.toml`, builds with `chatbot/Dockerfile` and deploys

## Step 2 — Set the API key (do NOT upload .env)

Never commit or upload the `.env` file — it exists only for local development and is
gitignored. On Railway, secrets are set as environment variables, encrypted at rest and
injected into the container at runtime:

1. Open the service → **Variables** tab
2. Add `ANTHROPIC_API_KEY` = `sk-ant-...`
3. (Optional) `MODEL` to override the default model
4. Railway redeploys automatically; the backend picks the key up via `os.getenv`

CLI alternative:

```bash
railway variables --set "ANTHROPIC_API_KEY=sk-ant-..."
```

## Step 3 — Publish the URL

Service → **Settings** → **Networking** → **Generate Domain**. The app is served at the
generated `*.up.railway.app` URL: the chat UI at `/`, the API under `/api/*`.

## Verify

```
GET https://<your-domain>/api/health
→ {"status":"ok","mode":"llm", ...}
```

If `mode` says `no-key`, the `ANTHROPIC_API_KEY` variable isn't set on the service.
