import DateCarousel from "@/components/DateCarousel";
import HomeClient from "@/components/HomeClient";
import { supabaseBuild } from "@/lib/supabase";
import type { Story } from "@/lib/types";
import { Suspense } from "react";

export const dynamic = "force-static";

async function fetchStories(): Promise<Story[]> {
  const sb = supabaseBuild();
  const { data, error } = await sb
    .from("stories")
    .select("*")
    .eq("is_active", true)
    .order("trending_score", { ascending: false })
    .order("last_updated", { ascending: false })
    .limit(100);
  if (error) {
    console.error("fetch stories failed", error);
    return [];
  }
  const stories = data as Story[];
  if (stories.length === 0) return stories;

  // Attach the distinct set of YYYY-MM-DD dates each story has events on,
  // so the client-side date filter can match stories by any timeline event.
  const ids = stories.map((s) => s.id);
  const { data: events, error: evErr } = await sb
    .from("timeline_events")
    .select("story_id,event_timestamp")
    .in("story_id", ids);
  if (evErr) {
    console.error("fetch story event dates failed", evErr);
    return stories;
  }
  const byStory = new Map<string, Set<string>>();
  for (const e of events as { story_id: string; event_timestamp: string }[]) {
    const day = (e.event_timestamp || "").slice(0, 10);
    if (!day) continue;
    if (!byStory.has(e.story_id)) byStory.set(e.story_id, new Set());
    byStory.get(e.story_id)!.add(day);
  }
  return stories.map((s) => ({
    ...s,
    event_dates: Array.from(byStory.get(s.id) ?? []).sort().reverse(),
  }));
}

export default async function HomePage() {
  const stories = await fetchStories();

  return (
    <div className="mx-auto max-w-6xl px-4 py-4">
      <Suspense fallback={<div className="h-10" />}>
        <HomeClient stories={stories} />
      </Suspense>
      <Suspense fallback={null}>
        <DateCarousel />
      </Suspense>
    </div>
  );
}
