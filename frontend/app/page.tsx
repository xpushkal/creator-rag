"use client";

import { useEffect, useState } from "react";
import VideoCard from "@/components/VideoCard";
import Chat from "@/components/Chat";
import { VideoMetadata, getVideos, ingestPair } from "@/lib/api";

export default function Home() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [instagramUrl, setInstagramUrl] = useState("");
  const [videos, setVideos] = useState<VideoMetadata[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getVideos().then(setVideos).catch(() => {});
  }, []);

  async function onIngest(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await ingestPair(youtubeUrl, instagramUrl);
      setVideos(
        Object.values(result).sort((a, b) => a.video_id.localeCompare(b.video_id)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setLoading(false);
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
    <main className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-8">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow">
            ▶
          </span>
          <h1 className="text-2xl font-bold tracking-tight">creator-rag</h1>
        </div>
        <p className="mt-2 text-sm text-neutral-500">
          Compare a YouTube video and an Instagram Reel — and ask why one
          outperformed the other.
        </p>
      </header>

      <form
        onSubmit={onIngest}
        className="mb-8 grid gap-3 rounded-2xl border border-neutral-200 bg-white/80 p-4 shadow-sm backdrop-blur sm:grid-cols-[1fr_1fr_auto]"
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
          className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-40"
        >
          {loading ? "Ingesting…" : "Ingest pair"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr_minmax(340px,1.1fr)]">
        {videos.map((v) => (
          <VideoCard key={v.video_id} video={v} isWinner={v.video_id === winnerId} />
        ))}
        {!ready &&
          Array.from({ length: Math.max(0, 2 - videos.length) }).map((_, i) => (
            <div
              key={`ph-${i}`}
              className="flex min-h-[260px] items-center justify-center rounded-2xl border border-dashed border-neutral-300 text-sm text-neutral-400"
            >
              awaiting ingest
            </div>
          ))}

        <div className="h-[600px]">
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
    <div className="flex items-center gap-2 rounded-xl border border-neutral-300 bg-white px-3 transition focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100">
      <span className="text-neutral-400">{icon}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent py-2.5 text-sm outline-none"
      />
    </div>
  );
}
