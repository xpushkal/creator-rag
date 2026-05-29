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

  // Load any previously ingested pair on mount.
  useEffect(() => {
    getVideos().then(setVideos).catch(() => {});
  }, []);

  async function onIngest(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await ingestPair(youtubeUrl, instagramUrl);
      setVideos(Object.values(result).sort((a, b) =>
        a.video_id.localeCompare(b.video_id),
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setLoading(false);
    }
  }

  const ready = videos.length >= 2;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">creator-rag</h1>
        <p className="text-sm text-neutral-500">
          Compare a YouTube video and an Instagram Reel — and ask why one
          outperformed the other.
        </p>
      </header>

      <form
        onSubmit={onIngest}
        className="mb-8 grid gap-3 rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm sm:grid-cols-[1fr_1fr_auto]"
      >
        <input
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          placeholder="YouTube URL"
          className="rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-500"
        />
        <input
          value={instagramUrl}
          onChange={(e) => setInstagramUrl(e.target.value)}
          placeholder="Instagram Reel URL"
          className="rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-500"
        />
        <button
          type="submit"
          disabled={loading || !youtubeUrl || !instagramUrl}
          className="rounded-lg bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {loading ? "Ingesting…" : "Ingest pair"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr_minmax(320px,1fr)]">
        {videos.map((v) => (
          <VideoCard key={v.video_id} video={v} />
        ))}
        {!ready &&
          Array.from({ length: 2 - videos.length }).map((_, i) => (
            <div
              key={`ph-${i}`}
              className="flex min-h-[220px] items-center justify-center rounded-2xl border border-dashed border-neutral-300 text-sm text-neutral-400"
            >
              awaiting ingest
            </div>
          ))}

        <div className="h-[560px] lg:row-span-1">
          <Chat enabled={ready} />
        </div>
      </div>
    </main>
  );
}
