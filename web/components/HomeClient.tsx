"use client";

import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import CategoryTabs from "@/components/CategoryTabs";
import Feed from "@/components/Feed";
import { CATEGORY_ORDER, type Category, type Story } from "@/lib/types";

export default function HomeClient({ stories }: { stories: Story[] }) {
  const sp = useSearchParams();
  const cat = (sp.get("cat") as Category) || "All";
  const date = sp.get("date"); // YYYY-MM-DD or null

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
    if (date) list = list.filter((s) => s.event_dates?.includes(date));
    return list;
  }, [stories, cat, date]);

  return (
    <>
      <CategoryTabs active={cat} categories={categories} />
      {date && (
        <div className="mt-2 flex items-center gap-2 text-sm text-gray-400">
          <span>Showing stories with updates on <span className="text-gray-200">{date}</span></span>
          <a
            href={cat === "All" ? "/" : `/?cat=${encodeURIComponent(cat)}`}
            className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-gray-300 hover:bg-white/10"
          >
            Clear date
          </a>
        </div>
      )}
      <div className="mt-4">
        {filtered.length === 0 ? (
          <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-8 text-center text-sm text-gray-400">
            No stories match this filter.
          </div>
        ) : (
          <Feed stories={filtered} />
        )}
      </div>
    </>
  );
}
