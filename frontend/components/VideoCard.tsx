import { VideoMetadata } from "@/lib/api";

function fmt(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}

const SOURCE_STYLE: Record<string, string> = {
  youtube: "bg-red-500/10 text-red-400 ring-red-500/30",
  instagram: "bg-fuchsia-500/10 text-fuchsia-400 ring-fuchsia-500/30",
};

export default function VideoCard({
  video,
  isWinner,
}: {
  video: VideoMetadata;
  isWinner: boolean;
}) {
  const er =
    video.engagement_rate === null ? "—" : `${video.engagement_rate.toFixed(2)}%`;
  const sourceClass =
    SOURCE_STYLE[video.source] ?? "bg-neutral-800 text-neutral-400 ring-neutral-700";

  return (
    <div
      className={`relative flex flex-col rounded-[1.25rem] border bg-white/5 p-4 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-500/10 ${
        isWinner
          ? "border-indigo-500/50 shadow-lg shadow-indigo-500/20 ring-1 ring-indigo-500/50"
          : "border-white/10"
      }`}
    >
      {isWinner && (
        <span className="absolute -top-3 left-4 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white shadow-lg shadow-indigo-500/40">
          ★ Higher engagement
        </span>
      )}

      <div className="mb-3 flex items-center justify-between">
        <span className="rounded-full bg-black/40 px-2.5 py-1 text-xs font-semibold text-neutral-300">
          Video {video.video_id}
        </span>
        <span
          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ring-1 ${sourceClass}`}
        >
          {video.source}
        </span>
      </div>

      <h3 className="mb-1 line-clamp-2 text-sm font-semibold leading-snug text-neutral-100">
        {video.title || video.caption || video.url}
      </h3>
      <p className="mb-4 text-xs font-medium text-neutral-500">
        {video.creator ? `@${video.creator}` : "unknown creator"}
        {video.follower_count !== null
          ? ` · ${fmt(video.follower_count)} followers`
          : ""}
      </p>

      <div
        className={`mb-4 rounded-xl p-4 text-center text-white transition-all ${
          isWinner
            ? "bg-gradient-to-br from-indigo-500 to-purple-600 shadow-inner"
            : "bg-black/30 border border-white/5"
        }`}
      >
        <div className="text-4xl font-extrabold tracking-tight">{er}</div>
        <div className="mt-1 text-[10px] font-semibold uppercase tracking-widest text-white/70">
          engagement rate
        </div>
      </div>

      <dl className="mb-4 grid grid-cols-3 gap-2 text-center text-xs">
        <Stat label="Views" value={fmt(video.views)} />
        <Stat label="Likes" value={fmt(video.likes)} />
        <Stat label="Comments" value={fmt(video.comments)} />
      </dl>

      {video.hashtags.length > 0 && (
        <div className="mt-auto flex flex-wrap gap-2 pt-2 border-t border-white/5">
          {video.hashtags.slice(0, 5).map((h) => (
            <span
              key={h}
              className="rounded-lg bg-black/20 px-2 py-1 text-[10px] font-medium text-neutral-400 hover:text-neutral-300 transition-colors"
            >
              #{h}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-black/20 py-2.5 border border-white/5">
      <div className="font-bold text-neutral-200">{value}</div>
      <div className="mt-0.5 text-[10px] font-medium uppercase tracking-widest text-neutral-500">
        {label}
      </div>
    </div>
  );
}
