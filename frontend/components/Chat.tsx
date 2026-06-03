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
  quantitative: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
  qualitative: "bg-sky-500/10 text-sky-400 border border-sky-500/20",
  hybrid: "bg-violet-500/10 text-violet-400 border border-violet-500/20",
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
          // Replace (don't mutate) the last message so the updater stays pure;
          // React 18 StrictMode invokes it twice in dev, which would otherwise
          // append each token twice ("TheThe engagement engagement...").
          const updated = { ...last };
          if (e.type === "token") updated.content += e.content;
          else if (e.type === "intent") updated.intent = e.intent;
          else if (e.type === "citations") updated.citations = e.citations;
          else if (e.type === "error") updated.error = e.message;
          next[next.length - 1] = updated;
          return next;
        });
      });
    } catch (err) {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = {
          ...next[next.length - 1],
          error: err instanceof Error ? err.message : "Request failed",
        };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[1.25rem] border border-white/10 bg-black/40 shadow-xl backdrop-blur-xl">
      <div className="flex items-center gap-3 border-b border-white/10 bg-white/5 px-5 py-4 backdrop-blur-md">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/20 text-xs text-indigo-300 shadow-inner">
          ✦
        </span>
        <span className="text-sm font-semibold text-neutral-200">Ask about the comparison</span>
      </div>

      <div ref={scrollRef} className="scroll-slim flex-1 space-y-6 overflow-y-auto p-5">
        {messages.length === 0 && (
          <div className="space-y-3 animate-slide-up">
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-500">Suggested Questions</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                disabled={!enabled || busy}
                className="block w-full rounded-2xl border border-white/5 bg-white/5 px-4 py-3 text-left text-sm text-neutral-300 transition-all hover:border-indigo-500/30 hover:bg-indigo-500/10 hover:text-indigo-200 disabled:opacity-40 disabled:pointer-events-none"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`animate-slide-up ${m.role === "user" ? "text-right" : "text-left"}`}>
            <div
              className={`inline-block max-w-[85%] rounded-3xl px-5 py-3 text-sm leading-relaxed shadow-lg ${
                m.role === "user"
                  ? "whitespace-pre-wrap rounded-br-sm bg-gradient-to-r from-indigo-600 to-purple-600 text-white"
                  : "rounded-bl-sm bg-white/10 text-neutral-200 border border-white/5 backdrop-blur-md"
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
                  <span className="typing-dot bg-neutral-400 h-1.5 w-1.5 rounded-full block"></span>
                  <span className="typing-dot bg-neutral-400 h-1.5 w-1.5 rounded-full block" style={{ animationDelay: "0.2s" }}></span>
                  <span className="typing-dot bg-neutral-400 h-1.5 w-1.5 rounded-full block" style={{ animationDelay: "0.4s" }}></span>
                </span>
              ) : null}
            </div>

            {m.role === "assistant" && m.intent && (
              <div className="mt-2">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${
                    INTENT_STYLE[m.intent] ?? "bg-neutral-800 text-neutral-400 border border-neutral-700"
                  }`}
                >
                  {m.intent}
                </span>
              </div>
            )}

            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {m.citations.map((c) => (
                  <span
                    key={c.chunk_id}
                    className="rounded-lg bg-black/30 px-2 py-1 text-[10px] font-medium text-neutral-400 border border-white/5"
                  >
                    Video {c.video_id} · chunk {c.chunk_id} · {c.modality}
                  </span>
                ))}
              </div>
            )}

            {m.role === "assistant" && m.error && (
              <div className="mt-2 inline-block rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-left text-xs text-red-400">
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
        className="border-t border-white/10 bg-white/5 p-4 backdrop-blur-md"
      >
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!enabled || busy}
            placeholder={enabled ? "Ask a question…" : "Ingest two videos first"}
            className="flex-1 rounded-2xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-neutral-100 placeholder-neutral-500 outline-none transition-all focus:border-indigo-500/50 focus:bg-black/60 focus:ring-4 focus:ring-indigo-500/10 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!enabled || busy || !input.trim()}
            className="flex items-center justify-center rounded-2xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-lg transition-all hover:scale-[1.02] hover:bg-indigo-500 hover:shadow-indigo-500/25 disabled:pointer-events-none disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
