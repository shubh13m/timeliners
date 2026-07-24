"use client";

import Link from "next/link";
import type { Story } from "@/lib/types";

function readTime(text?: string | null): string {
  if (!text) return "1 min";
  const words = text.split(/\s+/).length;
  const mins = Math.max(1, Math.round(words / 200));
  return `${mins} min read`;
}

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

type Props = { story: Story; active?: boolean };

export default function StoryCard({ story, active }: Props) {
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
      <h3 className="mb-2 text-base font-semibold text-white line-clamp-2">
        {story.title}
      </h3>
      {story.summary && (
        <p className="mb-3 text-sm text-gray-300 line-clamp-2">{story.summary}</p>
      )}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{readTime(story.summary)}</span>
        {story.trending_score > 1 && (
          <span className="text-orange-400">🔥 trending</span>
        )}
      </div>
    </Link>
  );
}
