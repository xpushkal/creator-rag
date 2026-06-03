"use client";

import { useEffect, useState } from "react";
import VideoCard from "@/components/VideoCard";
import Chat from "@/components/Chat";
import { IngestError, VideoMetadata, getVideos, ingestPair, seedDemo } from "@/lib/api";

export default function Home() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [instagramUrl, setInstagramUrl] = useState("");
  const [videos, setVideos] = useState<VideoMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    getVideos().then(setVideos).catch(() => {});
  }, []);

  // Tick an elapsed counter while ingesting so the long wait (scrape +
  // transcription, ~30-60s) doesn't look frozen.
  useEffect(() => {
    if (!loading) {
      setElapsed(0);
      return;
    }
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [loading]);

  const stage =
    elapsed < 15
      ? "Fetching metadata…"
      : elapsed < 45
        ? "Transcribing audio…"
        : "Embedding & finishing up…";

  async function onIngest(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setErrorCode(null);
    setLoading(true);
    try {
      const result = await ingestPair(youtubeUrl, instagramUrl);
      setVideos(
        Object.values(result).sort((a, b) => a.video_id.localeCompare(b.video_id)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
      setErrorCode(err instanceof IngestError ? err.code : "ingest_failed");
    } finally {
      setLoading(false);
    }
  }

  // Fallback when live scraping is blocked from the host's IP: load the
  // deterministic demo pair so visitors can still explore the full RAG flow.
  async function onLoadDemo() {
    setError(null);
    setErrorCode(null);
    setSeeding(true);
    try {
      const seeded = await seedDemo();
      setVideos(
        [...seeded].sort((a, b) => a.video_id.localeCompare(b.video_id)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load demo data");
      setErrorCode("ingest_failed");
    } finally {
      setSeeding(false);
    }
  }

  const ready = videos.length >= 2;

  // Highest engagement rate wins (ties → no winner highlighted).
  const rates = videos.map((v) => v.engagement_rate ?? -1);
  const maxRate = Math.max(...rates, -1);
  const winnerId =
    ready && rates.filter((r) => r === maxRate).length === 1
      ? videos[rates.indexOf(maxRate)].video_id
      : null;

  return (
    <main className="mx-auto max-w-6xl px-4 py-12 animate-slide-up">
      <header className="mb-12 flex flex-col items-center text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/20">
          <span className="text-2xl text-white">▶</span>
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
          creator<span className="text-indigo-400">-rag</span>
        </h1>
        <p className="mt-4 max-w-xl text-lg text-neutral-400">
          Compare a YouTube video and an Instagram Reel — and discover the deeper reasons why one outperformed the other.
        </p>
      </header>

      <form
        onSubmit={onIngest}
        className="mx-auto mb-12 grid max-w-4xl gap-4 rounded-3xl border border-white/10 bg-white/5 p-4 shadow-xl backdrop-blur-xl sm:grid-cols-[1fr_1fr_auto]"
      >
        <UrlInput
          value={youtubeUrl}
          onChange={setYoutubeUrl}
          placeholder="YouTube URL"
          icon="▶"
        />
        <UrlInput
          value={instagramUrl}
          onChange={setInstagramUrl}
          placeholder="Instagram Reel URL"
          icon="◎"
        />
        <button
          type="submit"
          disabled={loading || !youtubeUrl || !instagramUrl}
          className="group relative flex items-center justify-center overflow-hidden rounded-2xl bg-indigo-600 px-6 py-3.5 text-sm font-semibold text-white shadow-lg transition-all hover:scale-[1.02] hover:bg-indigo-500 hover:shadow-indigo-500/25 disabled:pointer-events-none disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
              Ingesting…
            </span>
          ) : (
            "Ingest Pair"
          )}
        </button>
      </form>

      {loading && (
        <div className="mx-auto mb-10 flex max-w-3xl items-center justify-center gap-3 rounded-2xl border border-indigo-500/20 bg-indigo-500/10 px-6 py-4 text-sm font-medium text-indigo-300 backdrop-blur-md">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-400/30 border-t-indigo-300"></span>
          {stage}
          <span className="tabular-nums text-indigo-400/70">{elapsed}s</span>
          <span className="text-indigo-400/50">· scraping + transcription can take up to a minute</span>
        </div>
      )}

      {error && errorCode === "scraping_blocked" ? (
        <div className="mx-auto mb-10 flex max-w-3xl flex-col items-center gap-4 rounded-2xl border border-indigo-500/20 bg-indigo-500/10 px-6 py-5 text-center text-sm font-medium text-indigo-200 backdrop-blur-md">
          <p className="max-w-xl leading-relaxed text-indigo-200/90">{error}</p>
          <button
            onClick={onLoadDemo}
            disabled={seeding}
            className="group inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg transition-all hover:scale-[1.02] hover:bg-indigo-500 hover:shadow-indigo-500/25 disabled:pointer-events-none disabled:opacity-50"
          >
            {seeding ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
                Loading…
              </>
            ) : (
              "Load example comparison →"
            )}
          </button>
        </div>
      ) : error ? (
        <div className="mx-auto mb-10 max-w-3xl rounded-2xl border border-red-500/20 bg-red-500/10 px-6 py-4 text-center text-sm font-medium text-red-400 backdrop-blur-md">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 lg:gap-6 lg:grid-cols-[1fr_1fr_minmax(320px,1.2fr)]">
        {videos.map((v) => (
          <VideoCard key={v.video_id} video={v} isWinner={v.video_id === winnerId} />
        ))}
        {!ready &&
          Array.from({ length: Math.max(0, 2 - videos.length) }).map((_, i) => (
            <div
              key={`ph-${i}`}
              className="flex min-h-[250px] items-center justify-center rounded-[1.25rem] border border-dashed border-white/10 bg-white/5 text-sm font-medium text-neutral-500 backdrop-blur-sm"
            >
              Awaiting ingest...
            </div>
          ))}

        <div className="h-[450px] lg:h-[500px]">
          <Chat enabled={ready} />
        </div>
      </div>
    </main>
  );
}

function UrlInput({
  value,
  onChange,
  placeholder,
  icon,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  icon: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-black/20 px-4 transition-all focus-within:border-indigo-500/50 focus-within:bg-black/40 focus-within:ring-4 focus-within:ring-indigo-500/10 hover:border-white/20">
      <span className="text-neutral-500">{icon}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent py-3.5 text-sm font-medium text-white placeholder-neutral-500 outline-none"
      />
    </div>
  );
}
