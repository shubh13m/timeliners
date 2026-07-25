"use client";

import Link from "next/link";
import { useMemo } from "react";
import { istDateAnchor } from "@/lib/dates";

type Props = {
  /** Currently selected date, YYYY-MM-DD. null = "All". */
  activeDate: string | null;
  /** All dates that have stories in the current category, DESC (newest first). */
  availableDates: string[];
  /** Today in the user's local timezone, YYYY-MM-DD. */
  today: string;
  /** Non-date URL params to preserve (e.g. cat). */
  preserveParams: Record<string, string>;
};

function hrefFor(
  target: { date?: string | null; all?: boolean },
  preserve: Record<string, string>,
  today: string
) {
  const qs = new URLSearchParams(preserve);
  if (target.all) {
    qs.set("all", "1");
  } else if (target.date && target.date !== today) {
    qs.set("date", target.date);
  }
  const s = qs.toString();
  return s ? `/?${s}` : "/";
}

function formatLabel(date: string, today: string): string {
  // Anchor both dates at IST noon so weekday/month formatting is stable
  // regardless of the viewer's local timezone.
  const d = istDateAnchor(date);
  const t = istDateAnchor(today);
  const diffDays = Math.round((t.getTime() - d.getTime()) / 86_400_000);
  const opts: Intl.DateTimeFormatOptions = { timeZone: "Asia/Kolkata" };
  const weekday = d.toLocaleDateString(undefined, { ...opts, weekday: "short" });
  const monthDay = d.toLocaleDateString(undefined, {
    ...opts,
    month: "short",
    day: "numeric",
  });
  const base = `${weekday}, ${monthDay}`;
  if (diffDays === 0) return `${base} · Today`;
  if (diffDays === 1) return `${base} · Yesterday`;
  return base;
}

export default function DateStepper({
  activeDate,
  availableDates,
  today,
  preserveParams,
}: Props) {
  // availableDates is DESC (newest first). Newer = smaller index, older =
  // larger index. Left arrow (‹) = newer, right arrow (›) = older.
  const { newerHref, olderHref } = useMemo(() => {
    if (activeDate === null) {
      // On "All" — left goes to newest date, right disabled.
      return {
        newerHref: availableDates[0]
          ? hrefFor({ date: availableDates[0] }, preserveParams, today)
          : null,
        olderHref: null,
      };
    }
    const idx = availableDates.indexOf(activeDate);
    // If current date isn't in availableDates (e.g. category changed and
    // this date has no stories in the new category), let the user jump to
    // the newest available date via the newer (‹) arrow. The older (›)
    // arrow is disabled to avoid the previous bug where both arrows led to
    // the same destination.
    if (idx === -1) {
      return {
        newerHref: availableDates[0]
          ? hrefFor({ date: availableDates[0] }, preserveParams, today)
          : null,
        olderHref: null,
      };
    }
    const newer = idx > 0 ? availableDates[idx - 1] : null;
    const older = idx < availableDates.length - 1 ? availableDates[idx + 1] : null;
    return {
      newerHref: newer ? hrefFor({ date: newer }, preserveParams, today) : null,
      olderHref: older ? hrefFor({ date: older }, preserveParams, today) : null,
    };
  }, [activeDate, availableDates, preserveParams, today]);

  const centerLabel = activeDate
    ? formatLabel(activeDate, today)
    : "All dates";

  const todayHref = hrefFor({ date: today }, preserveParams, today);
  const allHref = hrefFor({ all: true }, preserveParams, today);
  const allActive = activeDate === null;

  const arrowBase =
    "flex h-9 w-9 items-center justify-center rounded-full border border-white/10 text-lg leading-none transition";
  const arrowEnabled = "bg-white/5 text-gray-200 hover:border-red-500/60 hover:text-red-400";
  const arrowDisabled = "cursor-not-allowed bg-white/[0.02] text-gray-600";

  return (
    <div className="mt-3 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        {newerHref ? (
          <Link
            href={newerHref}
            aria-label="Newer date"
            className={`${arrowBase} ${arrowEnabled}`}
          >
            ‹
          </Link>
        ) : (
          <span aria-hidden className={`${arrowBase} ${arrowDisabled}`}>
            ‹
          </span>
        )}

        <Link
          href={todayHref}
          className="min-w-[10rem] rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-center text-sm font-medium text-gray-100 transition hover:border-red-500/60 hover:text-red-400"
          title="Jump to today"
        >
          {centerLabel}
        </Link>

        {olderHref ? (
          <Link
            href={olderHref}
            aria-label="Older date"
            className={`${arrowBase} ${arrowEnabled}`}
          >
            ›
          </Link>
        ) : (
          <span aria-hidden className={`${arrowBase} ${arrowDisabled}`}>
            ›
          </span>
        )}
      </div>

      <Link
        href={allActive ? todayHref : allHref}
        className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition ${
          allActive
            ? "border-red-500/60 bg-red-500/10 text-red-300"
            : "border-white/10 bg-white/5 text-gray-300 hover:border-red-500/60 hover:text-red-400"
        }`}
        title={allActive ? "Back to today" : "Show every date"}
      >
        All
      </Link>
    </div>
  );
}
