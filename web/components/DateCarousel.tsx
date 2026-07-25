"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

function formatDate(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function labelFor(d: Date, today: Date): string {
  const diff = Math.round(
    (today.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export default function DateCarousel({ days = 30 }: { days?: number }) {
  const sp = useSearchParams();
  const activeDate = sp.get("date");
  const cat = sp.get("cat");
  const showAll = sp.get("all") === "1";
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayKey = formatDate(today);

  const dates = Array.from({ length: days }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    return d;
  });

  const hrefWith = (params: URLSearchParams) => {
    const qs = params.toString();
    return qs ? `/?${qs}` : "/";
  };

  const hrefForDate = (key: string) => {
    const params = new URLSearchParams();
    if (cat) params.set("cat", cat);
    if (key !== todayKey) params.set("date", key);
    return hrefWith(params);
  };

  const hrefAll = () => {
    const params = new URLSearchParams();
    if (cat) params.set("cat", cat);
    params.set("all", "1");
    return hrefWith(params);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-white/10 bg-black/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto no-scrollbar px-3 py-2">
        <Link
          href={hrefAll()}
          className={`shrink-0 rounded-lg px-3 py-1.5 text-xs transition ${
            showAll
              ? "bg-red-600 text-white"
              : "bg-white/5 text-gray-300 hover:bg-white/10"
          }`}
        >
          All dates
        </Link>
        {dates.map((d) => {
          const key = formatDate(d);
          const on = !showAll && (activeDate === key || (!activeDate && key === todayKey));
          return (
            <Link
              key={key}
              href={hrefForDate(key)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-xs transition ${
                on
                  ? "bg-red-600 text-white"
                  : "bg-white/5 text-gray-300 hover:bg-white/10"
              }`}
            >
              {labelFor(d, today)}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
