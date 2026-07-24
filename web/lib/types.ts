export type Story = {
  id: string;
  title: string;
  slug: string;
  category: string;
  summary: string | null;
  trending_score: number;
  is_active: boolean;
  first_seen_at: string;
  last_updated: string;
  created_at: string;
};

export type TimelineEvent = {
  id: string;
  story_id: string;
  event_timestamp: string;
  headline: string;
  details: string | null;
  source_url: string | null;
  source_name: string | null;
  content_hash: string;
  event_type: "announcement" | "verdict" | "statement" | "update" | "correction";
  confidence: number;
  parent_event_id: string | null;
  created_at: string;
};

export type DailyDigest = {
  id: string;
  digest_date: string;
  story_id: string;
  summary_snippet: string | null;
  display_order: number;
  created_at: string;
};

export type StoryWithEvents = Story & { events: TimelineEvent[] };

export const CATEGORIES = [
  "All",
  "India Top News",
  "Politics",
  "Business",
  "Sports",
  "Technology",
  "World",
  "Entertainment",
] as const;

export type Category = (typeof CATEGORIES)[number];
