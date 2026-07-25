"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { Category } from "@/lib/types";

type Props = { active: Category; categories: Category[] };

export default function CategoryTabs({ active, categories }: Props) {
  const sp = useSearchParams();
  const date = sp.get("date");
  if (categories.length <= 1) return null; // no filter needed

  return (
    <nav
      aria-label="Filter stories by category"
      className="flex gap-1 overflow-x-auto no-scrollbar py-2"
    >
      {categories.map((cat) => {
        const params = new URLSearchParams();
        if (cat !== "All") params.set("cat", cat);
        if (date) params.set("date", date);
        const qs = params.toString();
        const href = qs ? `/?${qs}` : "/";
        const on = active === cat;
        return (
          <Link
            key={cat}
            href={href}
            aria-current={on ? "page" : undefined}
            className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 focus-visible:ring-offset-black ${
              on
                ? "bg-red-600 text-white"
                : "bg-white/5 text-gray-300 hover:bg-white/10"
            }`}
          >
            {cat}
          </Link>
        );
      })}
    </nav>
  );
}
