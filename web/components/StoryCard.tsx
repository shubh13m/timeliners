"use client";

import Link from "next/link";
import type { Story } from "@/lib/types";

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

type Props = { story: Story; active?: boolean };

export default function StoryCard({ story, active }: Props) {
  const eventCount = Math.max(1, story.trending_score || 1);
  return (
    <Link
      href={`/story/${story.slug}/`}
      className={`block rounded-xl border border-white/10 p-4 transition hover:border-blue-400/50 hover:bg-white/[0.03] ${
        active ? "border-blue-400 bg-blue-500/5" : "bg-white/[0.02]"
      }`}
    >
      <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
        <span className="rounded bg-white/5 px-2 py-0.5">{story.category}</span>
        <span>{timeAgo(story.last_updated)}</span>
      </div>
      <h3 className="text-base font-semibold leading-snug text-white line-clamp-3">
        {story.title}
      </h3>
      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <span>
          {eventCount} event{eventCount === 1 ? "" : "s"}
        </span>
        {story.trending_score > 2 && (
          <span className="text-orange-400">🔥 trending</span>
        )}
      </div>
    </Link>
  );
}
