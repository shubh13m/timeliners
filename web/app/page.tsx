import CategoryTabs from "@/components/CategoryTabs";
import DateCarousel from "@/components/DateCarousel";
import Feed from "@/components/Feed";
import { supabaseBuild } from "@/lib/supabase";
import type { Category, Story } from "@/lib/types";
import { Suspense } from "react";

export const dynamic = "force-static";

type Props = {
  searchParams: Promise<{ cat?: string; date?: string }>;
};

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
  return data as Story[];
}

export default async function HomePage({ searchParams }: Props) {
  const sp = await searchParams;
  const cat = (sp.cat as Category) || "All";
  const all = await fetchStories();
  const filtered = cat === "All" ? all : all.filter((s) => s.category === cat);

  return (
    <div className="mx-auto max-w-6xl px-4 py-4">
      <CategoryTabs active={cat} />
      <div className="mt-4">
        <Feed stories={filtered} />
      </div>
      <Suspense fallback={null}>
        <DateCarousel />
      </Suspense>
    </div>
  );
}
