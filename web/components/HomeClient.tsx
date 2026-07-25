"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import CategoryTabs from "@/components/CategoryTabs";
import DateStepper from "@/components/DateStepper";
import Feed from "@/components/Feed";
import { CATEGORY_ORDER, type Category, type Story } from "@/lib/types";

export default function HomeClient({ stories }: { stories: Story[] }) {
  const sp = useSearchParams();
  const cat = (sp.get("cat") as Category) || "All";
  const dateParam = sp.get("date"); // explicit YYYY-MM-DD
  const showAll = sp.get("all") === "1";

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
    const extras = [...present].filter(
      (c) => !CATEGORY_ORDER.includes(c as (typeof CATEGORY_ORDER)[number])
    );
    return [...ordered, ...extras];
  }, [stories]);

  // First narrow by category — the stepper should only walk through dates
  // that actually have stories in the selected category.
  const inCategory = useMemo(
    () => (cat === "All" ? stories : stories.filter((s) => s.category === cat)),
    [stories, cat]
  );

  // All dates present in the current category, sorted DESC (newest first).
  const availableDates = useMemo(() => {
    const set = new Set<string>();
    for (const s of inCategory) for (const d of s.event_dates ?? []) set.add(d);
    return [...set].sort().reverse();
  }, [inCategory]);

  // Default = today if today has stories in the current category, else the
  // newest date that does. "All" (showAll) opts out of date filtering.
  const effectiveDate = useMemo(() => {
    if (showAll) return null;
    if (dateParam) return dateParam;
    if (availableDates.includes(todayKey)) return todayKey;
    return availableDates[0] ?? null;
  }, [showAll, dateParam, availableDates, todayKey]);

  const filtered = useMemo(() => {
    let list = inCategory;
    if (effectiveDate) {
      list = list.filter((s) => s.event_dates?.includes(effectiveDate));
    }
    return [...list].sort((a, b) => {
      // Sort by the story's latest event timestamp (full precision, not
      // date-only). Two stories both updated today should be ordered by
      // time-of-day of their latest event, not by trending_score.
      const av = a.latest_event_at ?? a.last_updated ?? "";
      const bv = b.latest_event_at ?? b.last_updated ?? "";
      if (av !== bv) return bv.localeCompare(av);
      // Only reachable when two stories share the exact same latest
      // event timestamp — bigger timeline wins the tie.
      return (b.trending_score || 0) - (a.trending_score || 0);
    });
  }, [inCategory, effectiveDate]);

  const preserveParams = useMemo<Record<string, string>>(() => {
    const p: Record<string, string> = {};
    if (cat && cat !== "All") p.cat = cat;
    return p;
  }, [cat]);

  // If the selected date has zero results in the current category, suggest
  // the nearest available date instead of a dead-end.
  const suggestion = useMemo(() => {
    if (filtered.length > 0 || !effectiveDate) return null;
    const nearest = availableDates[0];
    if (!nearest) return null;
    const qs = new URLSearchParams(preserveParams);
    if (nearest !== todayKey) qs.set("date", nearest);
    return { date: nearest, href: qs.toString() ? `/?${qs.toString()}` : "/" };
  }, [filtered.length, effectiveDate, availableDates, preserveParams, todayKey]);

  return (
    <>
      <CategoryTabs active={cat} categories={categories} />
      <DateStepper
        activeDate={effectiveDate}
        availableDates={availableDates}
        today={todayKey}
        preserveParams={preserveParams}
      />
      <div className="mt-4 pb-20">
        {filtered.length === 0 ? (
          <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-8 text-center text-sm text-gray-400">
            {suggestion ? (
              <>
                No {cat === "All" ? "" : `${cat} `}stories on this date.{" "}
                <Link
                  href={suggestion.href}
                  className="text-red-400 hover:underline"
                >
                  Jump to {suggestion.date} →
                </Link>
              </>
            ) : (
              <>No stories yet.</>
            )}
          </div>
        ) : (
          <Feed stories={filtered} />
        )}
      </div>
    </>
  );
}
