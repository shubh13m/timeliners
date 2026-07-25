import HomeClient from "@/components/HomeClient";
import { supabaseBuild } from "@/lib/supabase";
import { istDate } from "@/lib/dates";
import type { Story } from "@/lib/types";
import { Suspense } from "react";

export const dynamic = "force-static";

async function fetchStories(): Promise<Story[]> {
  const sb = supabaseBuild();
  // NOTE: we don't order server-side by trending_score/last_updated because
  // that biases which 100 stories we pick. `last_updated` is set to ingest
  // run time (unreliable for backfilled rows), and trending_score = total
  // event count (rewards stale-but-large stories). Instead, pull the freshest
  // 100 by creation, then let the client sort by latest event date.
  const { data, error } = await sb
    .from("stories")
    .select("*")
    .eq("is_active", true)
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
  const counts = new Map<string, number>();
  // Track the max event_timestamp per story so the client can sort by the
  // real last-activity moment (not by ingest-run time or date-only).
  const latest = new Map<string, string>();
  for (const e of events as { story_id: string; event_timestamp: string }[]) {
    counts.set(e.story_id, (counts.get(e.story_id) ?? 0) + 1);
    const ts = e.event_timestamp || "";
    if (!ts) continue;
    const prev = latest.get(e.story_id);
    // ISO timestamps compare correctly as strings.
    if (!prev || ts > prev) latest.set(e.story_id, ts);
    // Bucket by IST day, not UTC day. An event at 20:00 UTC = 01:30 IST next
    // day should file under the IST date shown in the timeline panel, not
    // the UTC date underlying the raw timestamp.
    const day = istDate(ts);
    if (!byStory.has(e.story_id)) byStory.set(e.story_id, new Set());
    byStory.get(e.story_id)!.add(day);
  }
  return stories.map((s) => ({
    ...s,
    event_dates: Array.from(byStory.get(s.id) ?? []).sort().reverse(),
    event_count: counts.get(s.id) ?? 0,
    latest_event_at: latest.get(s.id) ?? s.last_updated,
  }));
}

export default async function HomePage() {
  const stories = await fetchStories();

  return (
    <div className="mx-auto max-w-6xl px-4 py-4">
      <Suspense fallback={<div className="h-10" />}>
        <HomeClient stories={stories} />
      </Suspense>
    </div>
  );
}
