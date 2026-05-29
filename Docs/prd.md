# PRD — creator-rag

| | |
|---|---|
| **Owner** | xPushkal |
| **Version** | 0.1 |
| **Related docs** | `README.md` (implementation + trade-offs) |

---

## 1. Summary

A chatbot that ingests two short-form videos — one from YouTube, one from an Instagram Reel — and answers natural-language questions comparing their content and performance. A creator should be able to ask *why* one video outperformed the other and get a grounded, cited answer, not a guess.

The product is a thin chat surface over a deliberately non-trivial backend: reliable cross-platform data extraction, deterministic handling of performance metrics, and semantic retrieval over transcripts.

## 2. Problem

Creators iterate on short-form video largely on instinct. They can see *that* one video did better, but the platforms give them dashboards of numbers, not explanations. The question they actually have — "what did the winning video do that the other didn't, and how do I repeat it?" — sits across two data types: hard engagement metrics and the qualitative content of the video itself. No single tool answers that question conversationally across platforms.

## 3. Goals and non-goals

**Goals**
- Accept two video URLs (one YouTube, one Instagram Reel) and produce a side-by-side, queryable comparison.
- Answer performance questions with arithmetically correct numbers and content questions with cited, grounded reasoning.
- Stream responses, cite sources, and hold context across a multi-turn conversation.
- Be honest and defensible about cost and scaling behavior.

**Non-goals (v1)**
- Not a general analytics dashboard; the interface is conversational.
- Not multi-account or auth-gated; inputs are public video URLs.
- Not real-time monitoring; ingestion is on-demand per pair.
- Not a recommendation engine that posts or schedules content.

## 4. Users

- **Primary: the individual creator.** Wants plain-language answers about what worked and concrete suggestions for the next video. Non-technical; cares about speed and trustworthy numbers.
- **Secondary: social/agency analyst.** Compares competitor content; values that the numbers are exact and the reasoning is traceable to a source.

## 5. Core use cases

The product must answer at least these five questions about the ingested pair:

| # | Question | Type |
|---|---|---|
| UC-1 | What's the engagement rate of each? | Quantitative |
| UC-2 | Who's the creator of Video B and what's their follower count? | Quantitative |
| UC-3 | Compare the hooks in the first 5 seconds. | Qualitative |
| UC-4 | Suggest improvements for B based on what worked in A. | Qualitative |
| UC-5 | Why did Video A get more engagement than Video B? | Hybrid |

These intentionally span three intents. UC-1 and UC-2 are facts that must be *computed or looked up*, never inferred. UC-3 and UC-4 are semantic and require retrieval over content. UC-5 needs both. The system's intent router is built around this split.

## 6. Functional requirements

**Ingestion**
- **FR-1** — Accept exactly two video URLs as input: one YouTube URL and one Instagram Reel URL (both mandatory).
- **FR-2** — For each video, extract metadata: creator, follower count, views, likes, comments, hashtags, upload date, and duration.
- **FR-3** — For each video, obtain a transcript. (YouTube: native transcript API. Instagram: transcribe downloaded audio, since Instagram provides none.)
- **FR-4** — Normalize both platforms to a single internal schema before any downstream processing.

**Processing & storage**
- **FR-5** — Compute engagement rate as `(likes + comments) / views × 100`, deterministically in code.
- **FR-6** — Chunk each transcript and embed the chunks.
- **FR-7** — Store chunks in a vector store, each tagged with its `video_id` (A or B) and modality.
- **FR-8** — Store structured metadata such that quantitative questions are answered by lookup/computation, not by vector similarity.

**Retrieval & chat**
- **FR-9** — Classify each incoming question as quantitative, qualitative, or hybrid, and route accordingly.
- **FR-10** — Quantitative questions are answered from structured metadata; qualitative from retrieved chunks; hybrid from both, reconciled.
- **FR-11** — Responses must stream token-by-token.
- **FR-12** — Responses must cite their sources: which video, and which chunk(s) for content claims, or the metadata source for numbers.
- **FR-13** — The conversation must maintain memory across turns (follow-ups resolve against prior context).

**Frontend**
- **FR-14** — Display the two videos as side-by-side cards showing key metadata and engagement rate.
- **FR-15** — Provide a chat panel alongside the cards; streamed answers and citations render inline.

## 7. Non-functional requirements

- **NFR-1 (Quality/correctness)** — Engagement rate and other numeric facts must be exact, every time. Zero tolerance for hallucinated metrics.
- **NFR-2 (Latency)** — Streaming should begin within ~2s of a question under normal load; ingestion of a pair completes in a timeframe acceptable for an interactive demo.
- **NFR-3 (Cost)** — Per-video ingest cost should be near-zero; per-query cost dominated by LLM synthesis and minimized by routing trivial questions away from the LLM.
- **NFR-4 (Scalability)** — Architecture must have a clear, stated path to 1,000 creators/day and a defensible answer for what changes at 10,000.
- **NFR-5 (Portability)** — External providers (Instagram metadata source, LLM, transcription) must be swappable via configuration, not code changes.
- **NFR-6 (Observability)** — Per-video and per-query cost/latency should be measurable, not estimated.

## 8. Architecture (summary)

A LangGraph agent routes each question down one of three paths — quantitative (SQL + compute), qualitative (vector retrieval), or hybrid (both, merged) — then a synthesis step streams a cited answer and persists conversation memory via a checkpointer. Structured metadata and vector chunks both live in one Postgres instance (pgvector). Embeddings are produced by a local open-source model. Full implementation rationale and trade-offs are in `README.md`.

## 9. Data requirements

- **Video record:** `video_id` (A/B), source, url, creator, follower_count, views, likes, comments, hashtags, upload_date, duration, title/caption, derived engagement_rate.
- **Chunk record:** `chunk_id`, `video_id`, modality (transcript / OCR / visual), text, optional start/end timestamps, embedding vector.
- Engagement rate is derived, not stored as a source value, so it can never drift from its inputs.

## 10. Acceptance criteria

The build is considered to meet the brief when:

- AC-1 — Given one real YouTube URL and one real Instagram Reel URL, the system ingests both and renders two cards with correct metadata and engagement rates.
- AC-2 — UC-1 through UC-5 each return a correct, relevant answer; numeric answers match the platform figures exactly.
- AC-3 — Every content answer cites the specific video and chunk it drew from.
- AC-4 — A follow-up question that depends on a prior turn is answered correctly using conversation memory.
- AC-5 — Responses visibly stream.
- AC-6 — The README states, with numbers, the cost model and what breaks at 10k users.

## 11. Constraints and assumptions

- Instagram offers no reliable public API for this data; extraction depends on a scraper, which is inherently fragile and subject to rate limits and terms-of-service considerations. The local provider is demo-grade; a managed provider is required for scale.
- Input videos are public.
- Short-form transcripts are small (often 100–300 words), which informs chunking and means the vector store is light at the target scale.

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Instagram extraction breaks or rate-limits | Demo fails | Provider behind a swappable interface; managed provider as fallback; test against live Reel before relying on it |
| Retriever returns numbers and they get treated as facts | Wrong metrics shown to user | Router sends all quantitative questions to deterministic computation, never retrieval |
| Synchronous transcription blocks under load | Throughput collapses at scale | Move transcription to an async job queue with worker pool |
| LLM cost grows with chat volume | Margin erosion at scale | Route trivial questions away from the LLM; cache transcripts/embeddings; cache common answers |
| Account ban from local scraper | Tooling becomes unusable | Treat local provider as demo-only; managed provider with proxies for production |

## 13. Scope and phasing

- **Phase 1 — Screening MVP:** both platforms ingesting, engagement computed, router with all three paths, streaming cited chat with memory, side-by-side frontend. Local Instagram provider acceptable here.
- **Phase 2 — Scale hardening:** managed Instagram provider, async ingestion queue, response/transcript caching, cost+latency instrumentation surfaced in UI.
- **Phase 3 — Depth:** multimodal hook analysis (OCR of on-screen text + vision captions of opening frames) as distinct chunk modalities; optional reranker if retrieval quality dips as catalogs grow.

## 14. Open questions

- Should follower count, which often requires an authenticated session on Instagram, be a hard requirement or best-effort when unavailable?
- For UC-3, is transcript-only acceptable for v1, or is multimodal hook analysis in scope for the screen?
- What is the acceptable upper bound on ingest latency for a live demo before async ingestion becomes mandatory?