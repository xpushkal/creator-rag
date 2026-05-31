"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Citation, ChatEvent, streamChat } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  citations?: Citation[];
  error?: string;
}

const SUGGESTIONS = [
  "What's the engagement rate of each?",
  "Compare the hooks in the first 5 seconds.",
  "Why did Video A get more engagement than Video B?",
];

const INTENT_STYLE: Record<string, string> = {
  quantitative: "bg-emerald-100 text-emerald-700",
  qualitative: "bg-sky-100 text-sky-700",
  hybrid: "bg-violet-100 text-violet-700",
};

export default function Chat({ enabled }: { enabled: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const threadId = useRef(`t-${Math.random().toString(36).slice(2)}`).current;
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

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
          else if (e.type === "error") last.error = e.message;
          return next;
        });
      });
    } catch (err) {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1].error =
          err instanceof Error ? err.message : "Request failed";
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-neutral-200 px-4 py-3">
        <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-indigo-600 text-xs text-white">
          ✦
        </span>
        <span className="text-sm font-semibold">Ask about the comparison</span>
      </div>

      <div ref={scrollRef} className="scroll-slim flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-neutral-400">Try asking</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                disabled={!enabled || busy}
                className="block w-full rounded-xl border border-neutral-200 px-3 py-2.5 text-left text-xs text-neutral-600 transition hover:border-indigo-300 hover:bg-indigo-50/50 disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className={`inline-block max-w-[88%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                m.role === "user"
                  ? "whitespace-pre-wrap rounded-br-md bg-neutral-900 text-white"
                  : "rounded-bl-md bg-neutral-100 text-neutral-900"
              }`}
            >
              {m.role === "assistant" && m.content ? (
                <div className="md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.content}
                  </ReactMarkdown>
                </div>
              ) : (
                m.content
              )}
              {m.role === "assistant" && busy && !m.content && !m.error ? (
                <span className="inline-flex gap-1">
                  <span className="typing-dot">●</span>
                  <span className="typing-dot" style={{ animationDelay: "0.2s" }}>●</span>
                  <span className="typing-dot" style={{ animationDelay: "0.4s" }}>●</span>
                </span>
              ) : null}
            </div>

            {m.role === "assistant" && m.intent && (
              <div className="mt-1.5">
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                    INTENT_STYLE[m.intent] ?? "bg-neutral-200 text-neutral-600"
                  }`}
                >
                  {m.intent}
                </span>
              </div>
            )}

            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {m.citations.map((c) => (
                  <span
                    key={c.chunk_id}
                    className="rounded-md bg-neutral-100 px-1.5 py-0.5 text-[10px] text-neutral-500 ring-1 ring-neutral-200"
                  >
                    Video {c.video_id} · chunk {c.chunk_id} · {c.modality}
                  </span>
                ))}
              </div>
            )}

            {m.role === "assistant" && m.error && (
              <div className="mt-1.5 inline-block rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-left text-xs text-amber-800">
                ⚠️ {m.error}
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
          placeholder={enabled ? "Ask a question…" : "Ingest two videos first"}
          className="flex-1 rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-neutral-100"
        />
        <button
          type="submit"
          disabled={!enabled || busy || !input.trim()}
          className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}
