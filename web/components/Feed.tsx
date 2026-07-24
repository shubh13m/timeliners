"use client";

import type { Story } from "@/lib/types";
import StoryCard from "./StoryCard";

type Props = { stories: Story[]; activeSlug?: string };

export default function Feed({ stories, activeSlug }: Props) {
  if (stories.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-8 text-center text-gray-400">
        No stories yet. The ingest worker runs 3× daily.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {stories.map((s) => (
        <StoryCard key={s.id} story={s} active={s.slug === activeSlug} />
      ))}
    </div>
  );
}
