import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import TimelinePanel from "@/components/TimelinePanel";
import { supabaseBuild } from "@/lib/supabase";
import { newsArticleJsonLd } from "@/lib/ld";
import type { Story, TimelineEvent } from "@/lib/types";

export const dynamic = "force-static";
export const dynamicParams = false;

type Params = { slug: string };

async function fetchAllSlugs(): Promise<string[]> {
  const sb = supabaseBuild();
  const { data, error } = await sb.from("stories").select("slug").limit(10000);
  if (error) {
    console.error("fetch slugs failed", error);
    return [];
  }
  return (data as { slug: string }[]).map((r) => r.slug);
}

async function fetchStory(slug: string): Promise<Story | null> {
  const sb = supabaseBuild();
  const { data } = await sb.from("stories").select("*").eq("slug", slug).maybeSingle();
  return (data as Story) || null;
}

async function fetchEvents(storyId: string): Promise<TimelineEvent[]> {
  const sb = supabaseBuild();
  const { data } = await sb
    .from("timeline_events")
    .select("*")
    .eq("story_id", storyId)
    .order("event_timestamp", { ascending: false });
  return (data as TimelineEvent[]) || [];
}

export async function generateStaticParams(): Promise<Params[]> {
  const slugs = await fetchAllSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { slug } = await params;
  const story = await fetchStory(slug);
  if (!story) return { title: "Story not found" };
  return {
    title: story.title,
    description: story.summary || undefined,
    openGraph: {
      title: story.title,
      description: story.summary || undefined,
      type: "article",
      publishedTime: story.first_seen_at,
      modifiedTime: story.last_updated,
      section: story.category,
    },
  };
}

export default async function StoryPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const story = await fetchStory(slug);
  if (!story) notFound();

  const events = await fetchEvents(story.id);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(newsArticleJsonLd(story, events)),
        }}
      />
      <Link
        href="/"
        className="mb-4 inline-block text-sm text-blue-400 hover:underline"
      >
        ← Back to feed
      </Link>
      <div className="mb-4 flex items-center gap-2 text-xs text-gray-400">
        <span className="rounded bg-white/5 px-2 py-0.5">{story.category}</span>
        <span>{events.length} events</span>
      </div>
      <h1 className="mb-3 text-2xl font-bold text-white sm:text-3xl">
        {story.title}
      </h1>
      {story.summary && (
        <p className="mb-6 text-gray-300">{story.summary}</p>
      )}
      <TimelinePanel events={events} />
    </div>
  );
}
