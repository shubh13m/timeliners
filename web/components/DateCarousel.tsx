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
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const dates = Array.from({ length: days }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    return d;
  });

  const hrefFor = (key: string) => {
    const params = new URLSearchParams();
    if (cat) params.set("cat", cat);
    if (key !== formatDate(today)) params.set("date", key);
    const qs = params.toString();
    return qs ? `/?${qs}` : "/";
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-white/10 bg-black/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto no-scrollbar px-3 py-2">
        {dates.map((d) => {
          const key = formatDate(d);
          const on = activeDate === key || (!activeDate && key === formatDate(today));
          return (
            <Link
              key={key}
              href={hrefFor(key)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-xs transition ${
                on
                  ? "bg-blue-500 text-white"
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
