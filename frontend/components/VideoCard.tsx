import { VideoMetadata } from "@/lib/api";

function fmt(n: number | null): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}

export default function VideoCard({ video }: { video: VideoMetadata }) {
  const er =
    video.engagement_rate === null
      ? "—"
      : `${video.engagement_rate.toFixed(2)}%`;

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <span className="rounded-full bg-neutral-900 px-2.5 py-0.5 text-xs font-semibold text-white">
          Video {video.video_id}
        </span>
        <span className="text-xs uppercase tracking-wide text-neutral-500">
          {video.source}
        </span>
      </div>

      <h3 className="mb-1 line-clamp-2 text-sm font-medium text-neutral-800">
        {video.title || video.caption || video.url}
      </h3>
      <p className="mb-4 text-xs text-neutral-500">
        {video.creator ? `@${video.creator}` : "unknown creator"}
        {video.follower_count !== null
          ? ` · ${fmt(video.follower_count)} followers`
          : ""}
      </p>

      <div className="mb-4 rounded-xl bg-neutral-900 p-3 text-center text-white">
        <div className="text-2xl font-bold">{er}</div>
        <div className="text-[10px] uppercase tracking-wide opacity-70">
          engagement rate
        </div>
      </div>

      <dl className="grid grid-cols-3 gap-2 text-center text-xs">
        <Stat label="Views" value={fmt(video.views)} />
        <Stat label="Likes" value={fmt(video.likes)} />
        <Stat label="Comments" value={fmt(video.comments)} />
      </dl>
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
