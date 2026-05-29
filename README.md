# creator-rag

A chatbot that compares two short-form videos — one YouTube, one Instagram Reel — and answers questions about why one outperformed the other.

The RAG part is the easy part. The hard part is everything around it: getting reliable data out of Instagram, and not letting a retriever hallucinate numbers. Most of the design effort went there.

---

## The one decision that matters

If you only read one section, read this one.

The five questions this bot has to answer are not the same kind of question:

- *"What's the engagement rate of each?"* → a **number**. It must be **computed**, never retrieved.
- *"Compare the hooks in the first 5 seconds."* → **semantic**. This is real retrieval.
- *"Why did A get more engagement than B?"* → **both**. Needs the numbers *and* the transcript reasoning.

Naive RAG embeds everything — including `"likes: 50000"` — into the vector store and retrieves by similarity. That's how you get a chatbot confidently reporting the wrong engagement rate, because cosine similarity over a number-as-text is meaningless.

So this isn't one pipeline. It's a **router** (built on LangGraph) that classifies the question and sends it down one of three paths:

```
                    ┌─────────────┐
   question ───────►│   ROUTER    │   classify intent
   + chat history   └──────┬──────┘
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        QUANTITATIVE   QUALITATIVE    HYBRID
        SQL + compute  vector search  (both, merged)
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │  SYNTHESIZE │   stream + cite + remember
                    └─────────────┘
```

Quantitative questions hit Postgres and compute `(likes + comments) / views * 100` in Python. The answer is *always* arithmetically correct, and it never touches the expensive LLM or the vector store. Qualitative questions retrieve transcript chunks tagged by video and cite them back. Hybrid questions do both and the synthesis step reconciles them.

This buys three things at once: correct numbers, lower cost (trivial questions are nearly free), and honest citations.

---

## How it works end to end

1. **Ingest.** You give it two URLs. The extraction layer normalizes both platforms to one schema (`VideoMetadata` + transcript). YouTube hands over a free transcript; Instagram does not, so its audio gets transcribed with Whisper.
2. **Store.** Metadata goes into a Postgres table (source of truth for the number questions). Transcripts are chunked, embedded with a local BGE model, and stored in the *same* Postgres via pgvector, each chunk tagged with `video_id` (A/B) and modality.
3. **Ask.** The LangGraph agent routes, answers, streams the response, cites which video and chunk it used, and keeps conversation memory across turns via a checkpointer.

---

## Stack, and why

> These are the trade-offs I'd defend on a call. Swap in your own reasoning where you disagree.

**Vector DB — pgvector (not Pinecone/Qdrant).** The router splits work into a SQL path and a vector path. pgvector lets both live in *one Postgres instance*: a video's metadata row and its chunks stay transactionally consistent, and there's no second service to operate. At the target scale (1000 creators/day → low hundreds of thousands of vectors) this is nowhere near Postgres's limits. A dedicated vector engine earns its keep at millions of vectors or sub-10ms latency SLAs — neither applies here, so paying for one would be premature.

**Embeddings — BGE, local (not OpenAI).** Open-source BGE is near the top of the MTEB retrieval board and runs on CPU at this volume. The transcripts are short; a hosted embedding API would be per-call spend for no measurable quality gain. Cost: $0.

**Orchestration — LangGraph (not bare LangChain).** A router is a graph with branches and a merge, not a linear chain. LangGraph also gives the checkpointer that backs cross-turn memory for free.

**Instagram extraction — dual provider.** See the next section; this is the riskiest part of the whole thing.

**Transcription — faster-whisper, local.** No per-minute API bill. Swap for AssemblyAI if you'd rather pay for managed accuracy.

---

## The Instagram problem (read before you trust the demo)

YouTube is trivial: `youtube-transcript-api` for the transcript, `yt-dlp` for metadata.

Instagram is the actual engineering. As of early 2026, `yt-dlp` is no longer reliable for Reels — it hits login walls and rate limits and fails to extract metadata. So the metadata provider here is **swappable by env var**:

- `IG_PROVIDER=instaloader` — free, runs locally, good enough for a two-video demo. But it rate-limits aggressively (429s), and heavy use can get the logged-in account banned. **Demo only.**
- `IG_PROVIDER=apify` — a managed scraper (~$1.50 per 1,000 posts) that handles proxies and anti-automation. **This is the production path.**

Both sit behind the same interface, so production is a config flag, not a rewrite.

And Instagram gives you **no transcript** — only metadata, caption, and a media URL. So the IG path downloads the media and runs Whisper on it, while the YouTube path skips Whisper entirely. The pipeline branches by source and converges to one schema.

> The `_download_media` step is intentionally left explicit in the code — it's the most fragile piece and the one most likely to break when Instagram changes their markup. Test it against a live Reel before relying on it.

---

## Chunking

Short-form transcripts are short — a Reel is often 100–200 words. Over-chunking a transcript that small produces near-duplicate chunks that pollute retrieval; under-chunking loses the granularity needed to answer "compare the hooks." The landing spot: sentence-window chunks of roughly **250 tokens with ~15% overlap**, plus a dedicated **hook chunk** built from every segment with `start < 5s` so the first-five-seconds question retrieves cleanly.

*(If you add multimodal later — OCR of on-screen text and a vision caption of the opening frames — those become their own modality-tagged chunks, which is what makes "compare the hooks" genuinely good rather than transcript-only.)*

---

## Cost model

Per-video ingest, production config:

| Step | Cost |
|---|---|
| YouTube metadata + transcript | $0 |
| Instagram metadata (Apify) | ~$0.0015 |
| Instagram transcript (local Whisper) | compute only |
| Embeddings (local BGE) | $0 |

Ingest is effectively free. The real marginal cost is **LLM tokens at query time**, dominated by the synthesis step. The router already routes quantitative questions away from the LLM entirely (SQL + format ≈ $0). Transcripts and embeddings are cached per video, so re-comparing a video that's already been processed costs nothing to ingest.

At 1000 creators/day (~2000 ingests), the Instagram metadata bill is around **$1.50/day**. Everything else is compute you already own.

> Verify current model prices when you fill in exact synthesis-cost numbers — they move.

---

## What breaks at 10,000 users

- **Transcription saturates first.** Synchronous Whisper calls will pin your CPU/GPU. Fix: a job queue (Redis + workers) with the API returning a job id and the client polling or subscribing over WebSocket. This is the real bottleneck, not the LLM.
- **Instaloader is no longer an option** — bans and rate limits make it unusable at scale. You must be on a managed scraper with rotating proxies by this point. (Already swappable.)
- **LLM cost scales linearly with chat volume.** Mitigations are already in place (router offloads quant queries) or cheap to add (cache answers to common questions; use a smaller synthesis model).
- **pgvector is still fine.** ~10k creators is still only low millions of vectors at most; an HNSW index handles it. Add pgbouncer for connection pooling before you add a separate vector DB.

---

## Setup

```bash
cp .env.example .env        # fill in keys
pip install -r requirements.txt

# Postgres with pgvector (docker is easiest)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=pass pgvector/pgvector:pg16

# Instaloader session (one time, local — never commit credentials)
instaloader -l YOUR_USERNAME

uvicorn app.api.main:app --reload
```

---

## Limitations / what I'd do next

- Multimodal hooks (OCR + vision captions) aren't wired yet — transcript-only answers to "compare the hooks" are shallower than they could be. This is the highest-value next step.
- Instagram extraction is inherently fragile; treat the local provider as best-effort.
- No reranker on retrieval yet; at this corpus size it isn't needed, but it's the obvious lever if answer quality dips as the catalog grows.