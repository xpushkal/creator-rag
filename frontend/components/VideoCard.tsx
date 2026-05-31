import { VideoMetadata } from "@/lib/api";

function fmt(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}

const SOURCE_STYLE: Record<string, string> = {
  youtube: "bg-red-50 text-red-600 ring-red-200",
  instagram: "bg-fuchsia-50 text-fuchsia-600 ring-fuchsia-200",
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
    SOURCE_STYLE[video.source] ?? "bg-neutral-100 text-neutral-600 ring-neutral-200";

  return (
    <div
      className={`relative flex flex-col rounded-2xl border bg-white p-5 shadow-sm transition ${
        isWinner
          ? "border-indigo-300 ring-2 ring-indigo-200"
          : "border-neutral-200"
      }`}
    >
      {isWinner && (
        <span className="absolute -top-2.5 left-5 rounded-full bg-indigo-600 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white shadow">
          ★ Higher engagement
        </span>
      )}

      <div className="mb-3 flex items-center justify-between">
        <span className="rounded-full bg-neutral-900 px-2.5 py-0.5 text-xs font-semibold text-white">
          Video {video.video_id}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ${sourceClass}`}
        >
          {video.source}
        </span>
      </div>

      <h3 className="mb-1 line-clamp-2 text-sm font-semibold leading-snug text-neutral-800">
        {video.title || video.caption || video.url}
      </h3>
      <p className="mb-4 text-xs text-neutral-500">
        {video.creator ? `@${video.creator}` : "unknown creator"}
        {video.follower_count !== null
          ? ` · ${fmt(video.follower_count)} followers`
          : ""}
      </p>

      <div
        className={`mb-4 rounded-xl p-4 text-center text-white ${
          isWinner
            ? "bg-gradient-to-br from-indigo-600 to-violet-600"
            : "bg-neutral-900"
        }`}
      >
        <div className="text-3xl font-bold tracking-tight">{er}</div>
        <div className="text-[10px] uppercase tracking-widest opacity-70">
          engagement rate
        </div>
      </div>

      <dl className="mb-4 grid grid-cols-3 gap-2 text-center text-xs">
        <Stat label="Views" value={fmt(video.views)} />
        <Stat label="Likes" value={fmt(video.likes)} />
        <Stat label="Comments" value={fmt(video.comments)} />
      </dl>

      {video.hashtags.length > 0 && (
        <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
          {video.hashtags.slice(0, 5).map((h) => (
            <span
              key={h}
              className="rounded-md bg-neutral-100 px-1.5 py-0.5 text-[10px] text-neutral-500"
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
    <div className="rounded-lg bg-neutral-100 py-2">
      <div className="font-semibold text-neutral-800">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-neutral-500">
        {label}
      </div>
    </div>
  );
}
