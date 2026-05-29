"use client";

import { useRef, useState } from "react";
import { Citation, ChatEvent, streamChat } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  citations?: Citation[];
}

const SUGGESTIONS = [
  "What's the engagement rate of each?",
  "Compare the hooks in the first 5 seconds.",
  "Why did Video A get more engagement than Video B?",
];

export default function Chat({ enabled }: { enabled: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const threadId = useRef(
    `t-${Math.random().toString(36).slice(2)}`,
  ).current;

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [
      ...m,
      { role: "user", content: q },
      { role: "assistant", content: "" },
    ]);

    try {
      await streamChat(q, threadId, (e: ChatEvent) => {
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          if (last.role !== "assistant") return next;
          if (e.type === "token") last.content += e.content;
          else if (e.type === "intent") last.intent = e.intent;
          else if (e.type === "citations") last.citations = e.citations;
          return next;
        });
      });
    } catch (err) {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1].content =
          `⚠️ ${err instanceof Error ? err.message : "Request failed"}`;
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-neutral-200 bg-white shadow-sm">
      <div className="border-b border-neutral-200 px-4 py-3 text-sm font-semibold">
        Ask about the comparison
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs text-neutral-500">Try asking:</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                disabled={!enabled || busy}
                className="block w-full rounded-lg border border-neutral-200 px-3 py-2 text-left text-xs hover:bg-neutral-50 disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={m.role === "user" ? "text-right" : "text-left"}
          >
            <div
              className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                m.role === "user"
                  ? "bg-neutral-900 text-white"
                  : "bg-neutral-100 text-neutral-900"
              }`}
            >
              {m.content || (busy ? "…" : "")}
            </div>
            {m.role === "assistant" && m.intent && (
              <div className="mt-1 text-[10px] uppercase tracking-wide text-neutral-400">
                routed: {m.intent}
              </div>
            )}
            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {m.citations.map((c) => (
                  <span
                    key={c.chunk_id}
                    className="rounded bg-neutral-200 px-1.5 py-0.5 text-[10px] text-neutral-700"
                  >
                    Video {c.video_id} · chunk {c.chunk_id} · {c.modality}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 border-t border-neutral-200 p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={!enabled || busy}
          placeholder={
            enabled ? "Ask a question…" : "Ingest two videos first"
          }
          className="flex-1 rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-500 disabled:bg-neutral-100"
        />
        <button
          type="submit"
          disabled={!enabled || busy || !input.trim()}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}
