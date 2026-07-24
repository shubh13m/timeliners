import Feed from "@/components/Feed";
import { supabaseBuild } from "@/lib/supabase";
import type { Story } from "@/lib/types";

export const dynamic = "force-static";

export const metadata = {
  title: "Archive",
  description: "All past stories from Timelined, active and inactive.",
};

async function fetchAll(): Promise<Story[]> {
  const sb = supabaseBuild();
  const { data } = await sb
    .from("stories")
    .select("*")
    .order("last_updated", { ascending: false })
    .limit(500);
  return (data as Story[]) || [];
}

export default async function ArchivePage() {
  const stories = await fetchAll();

  const byMonth = new Map<string, Story[]>();
  for (const s of stories) {
    const d = new Date(s.last_updated);
    const key = d.toLocaleDateString("en-IN", { year: "numeric", month: "long" });
    if (!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key)!.push(s);
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="mb-6 text-2xl font-bold text-white">Archive</h1>
      {[...byMonth.entries()].map(([month, list]) => (
        <section key={month} className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-400">
            {month} · {list.length}
          </h2>
          <Feed stories={list} />
        </section>
      ))}
    </div>
  );
}
