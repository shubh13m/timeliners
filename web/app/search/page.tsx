"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Feed from "@/components/Feed";
import { supabaseBrowser } from "@/lib/supabase";
import type { Story } from "@/lib/types";

function SearchInner() {
  const sp = useSearchParams();
  const q = sp.get("q") || "";
  const [results, setResults] = useState<Story[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!q) return;
    setLoading(true);
    setError(null);
    const sb = supabaseBrowser();
    sb.rpc("search_stories", { q, lim: 30 })
      .then(async ({ data, error }) => {
        if (error) {
          console.error(error);
          setError("Search failed. Please try again in a moment.");
          setResults([]);
          setLoading(false);
          return;
        }
        const stories = ((data as Story[]) || []).slice();
        if (stories.length === 0) {
          setResults(stories);
          setLoading(false);
          return;
        }
        // The search RPC only returns raw story rows. Hydrate the same
        // per-story event fields the homepage uses (event_count and
        // latest_event_at) so cards render the correct count and "X ago"
        // chip instead of falling back to trending_score / last_updated.
        const ids = stories.map((s) => s.id);
        const { data: events, error: evErr } = await sb
          .from("timeline_events")
          .select("story_id,event_timestamp")
          .in("story_id", ids);
        if (evErr) {
          console.error("hydrate search results failed", evErr);
          setResults(stories);
          setLoading(false);
          return;
        }
        const counts = new Map<string, number>();
        const latest = new Map<string, string>();
        for (const e of (events as { story_id: string; event_timestamp: string }[]) || []) {
          counts.set(e.story_id, (counts.get(e.story_id) ?? 0) + 1);
          const ts = e.event_timestamp || "";
          const prev = latest.get(e.story_id);
          if (ts && (!prev || ts > prev)) latest.set(e.story_id, ts);
        }
        setResults(
          stories.map((s) => ({
            ...s,
            event_count: counts.get(s.id) ?? 0,
            latest_event_at: latest.get(s.id) ?? s.last_updated,
          }))
        );
        setLoading(false);
      });
  }, [q]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="mb-4 text-2xl font-bold text-white">
        Search results {q && <span className="text-gray-400">· “{q}”</span>}
      </h1>
      {loading && <p className="text-gray-400">Searching…</p>}
      {error && !loading && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200"
        >
          {error}
        </div>
      )}
      {!loading && !error && q && results.length === 0 && (
        <p className="text-gray-400">No stories matched.</p>
      )}
      {!loading && !q && (
        <p className="text-gray-400">Type a query in the search bar above.</p>
      )}
      {results.length > 0 && <Feed stories={results} />}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-6 text-gray-400">Loading…</div>}>
      <SearchInner />
    </Suspense>
  );
}
