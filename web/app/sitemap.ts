import type { MetadataRoute } from "next";
import { supabaseBuild } from "@/lib/supabase";

export const dynamic = "force-static";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://timelined.pages.dev";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const sb = supabaseBuild();
  // Only surface active stories in the sitemap — archived stories still
  // exist for the /archive page but shouldn't consume Google's crawl budget
  // or serve as landing pages for search traffic.
  const { data } = await sb
    .from("stories")
    .select("slug,last_updated")
    .eq("is_active", true)
    .limit(10000);
  const stories = (data as { slug: string; last_updated: string }[]) || [];

  const base: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, priority: 1.0, changeFrequency: "hourly" },
    { url: `${SITE_URL}/archive/`, priority: 0.5, changeFrequency: "daily" },
  ];
  const storyEntries: MetadataRoute.Sitemap = stories.map((s) => ({
    url: `${SITE_URL}/story/${s.slug}/`,
    lastModified: new Date(s.last_updated),
    priority: 0.7,
    changeFrequency: "hourly",
  }));

  return [...base, ...storyEntries];
}
