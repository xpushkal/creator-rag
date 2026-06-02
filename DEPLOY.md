# Deploying creator-rag

This app is two pieces with very different hosting needs:

- **Frontend** (Next.js) → **Vercel**. Trivial; it's just a client.
- **Backend** (FastAPI + PyTorch/BGE + Whisper) → **Render** (a container host).
  It can't run on Vercel: PyTorch alone exceeds Vercel's 250 MB function limit,
  ingestion runs longer than serverless timeouts, and LangGraph's in-process
  memory doesn't survive serverless invocations.
- **Database** → **Neon** (serverless Postgres with pgvector).

Everything deploys from this GitHub repo. Order: **Neon → Render → Vercel**.

---

## 1. Database — Neon (pgvector)

1. Create a project at <https://neon.tech> (free tier).
2. Copy the connection string. It looks like:
   `postgresql://USER:PASSWORD@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`
3. **Rewrite the scheme** to the psycopg driver this app uses — change
   `postgresql://` to `postgresql+psycopg://`, keep `?sslmode=require`:
   ```
   postgresql+psycopg://USER:PASSWORD@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
   ```
   Save this as `DATABASE_URL` for the next step. The app enables the `vector`
   extension and creates its tables automatically on first boot.

---

## 2. Backend — Render (Docker Blueprint)

1. Push this repo to GitHub (already wired to `origin`).
2. In Render: **New → Blueprint**, pick this repo. Render reads
   [`render.yaml`](render.yaml) and provisions the `creator-rag-api` web service.
3. When prompted, fill the secret env vars (the rest are pre-filled):
   - `DATABASE_URL` — the Neon string from step 1.
   - `LLM_API_KEY` — your Groq key (`gsk_...`) from <https://console.groq.com>.
     Groq's free tier covers routing, synthesis, **and** Whisper transcription.
   - `CORS_ORIGINS` — leave blank for now; set it in step 4 once you have the
     Vercel URL.
4. Deploy. When it's live, copy the service URL, e.g.
   `https://creator-rag-api.onrender.com`. Verify: open `/health` → `{"status":"ok"}`.

> **Free-tier notes (expected, not bugs):**
> - The free instance **sleeps after ~15 min idle**; the next request cold-starts
>   (~50s, plus first-time download of the BGE model). The frontend already shows
>   an elapsed timer during ingestion.
> - Free RAM is **512 MB**. Loading the BGE embedding model can run close to that.
>   If you see out-of-memory restarts, bump the instance to the next tier (1 GB).
> - **Live YouTube/Instagram extraction often fails from cloud IPs** (both
>   platforms block datacenter ranges — see the README). For a reliable hosted
>   demo, seed deterministic data instead of relying on live scraping: from the
>   Render shell run `python -m scripts.seed`, or switch `IG_PROVIDER=apify` and
>   add a YouTube cookie/proxy.

---

## 3. Frontend — Vercel

1. In Vercel: **Add New → Project**, import this repo.
2. Set **Root Directory** to `frontend` (the Next.js app lives there).
3. Add an environment variable:
   - `NEXT_PUBLIC_API_BASE` = your Render URL (e.g.
     `https://creator-rag-api.onrender.com`) — **no trailing slash**.
4. Deploy. Copy the resulting URL (e.g. `https://creator-rag.vercel.app`).

---

## 4. Close the CORS loop

Back in Render, set `CORS_ORIGINS` to your Vercel URL and save (this redeploys):

```
CORS_ORIGINS=https://creator-rag.vercel.app
```

If you also use Vercel preview URLs, add them comma-separated. Then reload the
Vercel site — the chat and ingest calls should now reach the backend.

---

## Quick local sanity check (optional)

Build and run the backend container exactly as Render will:

```bash
docker build -t creator-rag-api .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL='postgresql+psycopg://...:...@.../...?sslmode=require' \
  -e LLM_API_KEY='gsk_...' \
  -e CORS_ORIGINS='http://localhost:3000' \
  creator-rag-api
# → http://localhost:8000/health
```
