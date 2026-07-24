"use client";

import Link from "next/link";
import { CATEGORIES, Category } from "@/lib/types";

type Props = { active: Category };

export default function CategoryTabs({ active }: Props) {
  return (
    <nav className="flex gap-1 overflow-x-auto no-scrollbar py-2">
      {CATEGORIES.map((cat) => {
        const href = cat === "All" ? "/" : `/?cat=${encodeURIComponent(cat)}`;
        const on = active === cat;
        return (
          <Link
            key={cat}
            href={href}
            className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm transition ${
              on
                ? "bg-blue-500 text-white"
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
