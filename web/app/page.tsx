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
  return data as Story[];
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
