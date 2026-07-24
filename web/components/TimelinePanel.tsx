"use client";

import type { TimelineEvent } from "@/lib/types";

const EVENT_ICON: Record<string, string> = {
  announcement: "📣",
  verdict: "⚖️",
  statement: "💬",
  update: "•",
  correction: "✏️",
};

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}

type Props = { events: TimelineEvent[] };

export default function TimelinePanel({ events }: Props) {
  const sorted = [...events].sort(
    (a, b) =>
      new Date(b.event_timestamp).getTime() -
      new Date(a.event_timestamp).getTime()
  );

  if (sorted.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-8 text-center text-gray-400">
        No events yet.
      </div>
    );
  }

  return (
    <ol className="relative border-l-2 border-white/10 pl-6">
      {sorted.map((e) => (
        <li key={e.id} className="relative mb-6 last:mb-0">
          <span className="absolute -left-[33px] flex h-6 w-6 items-center justify-center rounded-full bg-blue-500 text-xs">
            {EVENT_ICON[e.event_type] || "•"}
          </span>
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
            <div className="mb-1 flex items-center justify-between text-xs text-gray-400">
              <time>{fmtDate(e.event_timestamp)}</time>
              {e.event_type !== "update" && (
                <span className="rounded bg-white/5 px-2 py-0.5 capitalize">
                  {e.event_type}
                </span>
              )}
            </div>
            <h4 className="mb-1 font-semibold text-white">{e.headline}</h4>
            {e.details && (
              <p className="text-sm text-gray-300">{e.details}</p>
            )}
            {e.source_url && (
              <a
                href={e.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-xs text-blue-400 hover:underline"
              >
                {e.source_name || "Source"} ↗
              </a>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
