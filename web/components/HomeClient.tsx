"use client";

import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import CategoryTabs from "@/components/CategoryTabs";
import Feed from "@/components/Feed";
import { CATEGORY_ORDER, type Category, type Story } from "@/lib/types";

export default function HomeClient({ stories }: { stories: Story[] }) {
  const sp = useSearchParams();
  const cat = (sp.get("cat") as Category) || "All";
  const dateParam = sp.get("date"); // explicit YYYY-MM-DD
  const showAll = sp.get("all") === "1";

  // Default: the most recent date that actually has events (usually today
  // during normal cron ingest; falls back to the latest backfill day when
  // no fresh ingest has run yet). Users opt in to "All dates" to see history.
  const latestEventDate = useMemo(() => {
    let latest = "";
    for (const s of stories) {
      for (const d of s.event_dates ?? []) {
        if (d > latest) latest = d;
      }
    }
    return latest || null;
  }, [stories]);
  const effectiveDate = showAll ? null : dateParam || latestEventDate;

  const todayKey = useMemo(() => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }, []);

  // Categories that actually exist in the current story set (+ "All").
  const categories = useMemo<Category[]>(() => {
    const present = new Set(stories.map((s) => s.category).filter(Boolean));
    const ordered = CATEGORY_ORDER.filter((c) => c === "All" || present.has(c));
    const extras = [...present].filter((c) => !CATEGORY_ORDER.includes(c as (typeof CATEGORY_ORDER)[number]));
    return [...ordered, ...extras];
  }, [stories]);

  const filtered = useMemo(() => {
    let list = stories;
    if (cat !== "All") list = list.filter((s) => s.category === cat);
    if (effectiveDate) {
      list = list.filter((s) => s.event_dates?.includes(effectiveDate));
    }
    // Sort by the story's most recent timeline event (event_dates is stored
    // in descending order, so event_dates[0] is the latest activity). This
    // beats trending_score, which just counts total events and can float
    // stale-but-large stories to the top.
    return [...list].sort((a, b) => {
      const av = a.event_dates?.[0] ?? a.last_updated ?? "";
      const bv = b.event_dates?.[0] ?? b.last_updated ?? "";
      if (av !== bv) return bv.localeCompare(av);
      // Tiebreaker: bigger timelines first (more established stories).
      return (b.trending_score || 0) - (a.trending_score || 0);
    });
  }, [stories, cat, effectiveDate]);

  const dateLabel = effectiveDate === todayKey ? "today" : effectiveDate;

  return (
    <>
      <CategoryTabs active={cat} categories={categories} />
      {effectiveDate && (
        <div className="mt-2 flex items-center gap-2 text-sm text-gray-400">
          <span>
            Showing stories with updates on{" "}
            <span className="text-gray-200">{dateLabel}</span>
          </span>
        </div>
      )}
      <div className="mt-4 pb-20">
        {filtered.length === 0 ? (
          <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-8 text-center text-sm text-gray-400">
            No stories on this date.{" "}
            <a
              href={cat === "All" ? "/?all=1" : `/?cat=${encodeURIComponent(cat)}&all=1`}
              className="text-blue-400 hover:underline"
            >
              See all dates →
            </a>
          </div>
        ) : (
          <Feed stories={filtered} />
        )}
      </div>
    </>
  );
}
