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
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `Ingest failed (${res.status})`);
  }
  const data = await res.json();
  return data.videos as Record<string, VideoMetadata>;
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
