import type { Story, TimelineEvent } from "./types";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://timeliner.pages.dev";

export function newsArticleJsonLd(story: Story, events: TimelineEvent[]) {
  const first = events[events.length - 1];
  const last = events[0];
  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: story.title,
    description: story.summary || undefined,
    datePublished: first?.event_timestamp || story.first_seen_at,
    dateModified: last?.event_timestamp || story.last_updated,
    articleSection: story.category,
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${SITE_URL}/story/${story.slug}/`,
    },
    author: { "@type": "Organization", name: "Timeliner" },
    publisher: {
      "@type": "Organization",
      name: "Timeliner",
      logo: { "@type": "ImageObject", url: `${SITE_URL}/icon-512.png` },
    },
    image: [`${SITE_URL}/og-default.png`],
  };
}

export function siteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Timeliner",
    url: SITE_URL,
    potentialAction: {
      "@type": "SearchAction",
      target: `${SITE_URL}/search/?q={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  };
}
