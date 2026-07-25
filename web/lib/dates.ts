/**
 * Date utilities that keep the app on **Indian Standard Time**.
 *
 * The site is India-focused: cron ingest runs on IST, editors think in IST,
 * timeline events render in IST. But raw timestamps in Supabase are UTC. If
 * we bucket or filter by the UTC date, an event that happened at 04:30 IST
 * on Sat lands in the Fri UTC bucket, which then shows up in the wrong day
 * on the homepage and in the DateStepper. These helpers fix that by doing
 * every date-level operation in `Asia/Kolkata`.
 *
 * `en-CA` locale is used because it happens to format dates as YYYY-MM-DD
 * out of the box, which round-trips cleanly with ISO date strings.
 */
const IST = "Asia/Kolkata";

/** Convert any ISO timestamp (or Date) to `YYYY-MM-DD` in IST. */
export function istDate(iso: string | Date): string {
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: IST });
}

/** Today's `YYYY-MM-DD` in IST. Safe to call from any timezone. */
export function istToday(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: IST });
}

/**
 * Anchor a `YYYY-MM-DD` IST date string to a real Date at IST noon. Use this
 * when you need to format the date (weekday, month) — formatting a bare
 * `YYYY-MM-DD` via `new Date(...)` parses as local midnight, which drifts
 * across timezones and can flip the weekday.
 */
export function istDateAnchor(date: string): Date {
  return new Date(`${date}T12:00:00+05:30`);
}
