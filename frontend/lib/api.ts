// Thin client over the FastAPI backend.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface VideoMetadata {
  video_id: string;
  source: string;
  url: string;
  creator: string | null;
  follower_count: number | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  hashtags: string[];
  upload_date: string | null;
  duration: number | null;
  title: string | null;
  caption: string | null;
  engagement_rate: number | null;
}

export interface Citation {
  video_id: string;
  chunk_id: number;
  modality: string;
  start: number | null;
  end: number | null;
}

// Carries the backend's error `code` (e.g. "scraping_blocked") so the UI can
// react differently to a cloud-IP block vs. a genuine failure.
export class IngestError extends Error {
  code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = "IngestError";
    this.code = code;
  }
}

export async function ingestPair(
  youtube_url: string,
  instagram_url: string,
): Promise<Record<string, VideoMetadata>> {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ youtube_url, instagram_url }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    // New structured form: { code, message }. Fall back to legacy string detail.
    if (detail && typeof detail === "object") {
      throw new IngestError(
        detail.message ?? "Ingest failed",
        detail.code ?? "ingest_failed",
      );
    }
    throw new IngestError(
      typeof detail === "string" ? detail : `Ingest failed (${res.status})`,
      "ingest_failed",
    );
  }
  const data = await res.json();
  return data.videos as Record<string, VideoMetadata>;
}

// Loads the deterministic demo pair (POST /seed). Used as the fallback when
// live scraping is blocked from the host's IP. Idempotent on the backend.
export async function seedDemo(): Promise<VideoMetadata[]> {
  const res = await fetch(`${API_BASE}/seed`, { method: "POST" });
  if (!res.ok) throw new Error(`Could not load demo data (${res.status})`);
  const data = await res.json();
  return data.videos as VideoMetadata[];
}

export async function getVideos(): Promise<VideoMetadata[]> {
  const res = await fetch(`${API_BASE}/videos`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.videos as VideoMetadata[];
}

export type ChatEvent =
  | { type: "intent"; intent: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "token"; content: string }
  | { type: "error"; message: string }
  | { type: "done" };

// Streams SSE events from POST /chat, invoking onEvent for each one.
export async function streamChat(
  message: string,
  thread_id: string,
  onEvent: (e: ChatEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id }),
  });
  if (!res.body) throw new Error("No response stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)) as ChatEvent);
      } catch {
        // ignore malformed frame
      }
    }
  }
}
