import { supabaseBuild } from "@/lib/supabase";
import type { Story } from "@/lib/types";

export const dynamic = "force-static";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://timeliner.pages.dev";

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET(): Promise<Response> {
  const sb = supabaseBuild();
  const { data } = await sb
    .from("stories")
    .select("*")
    .eq("is_active", true)
    .order("last_updated", { ascending: false })
    .limit(50);
  const stories = (data as Story[]) || [];

  const items = stories
    .map((s) => {
      const link = `${SITE_URL}/story/${s.slug}/`;
      return `
    <item>
      <title>${escapeXml(s.title)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${new Date(s.last_updated).toUTCString()}</pubDate>
      <category>${escapeXml(s.category)}</category>
      ${s.summary ? `<description>${escapeXml(s.summary)}</description>` : ""}
    </item>`;
    })
    .join("");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Timeliner</title>
    <link>${SITE_URL}/</link>
    <description>Indian news as interactive timelines</description>
    <language>en-in</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    ${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
}
