"use client";

import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import CategoryTabs from "@/components/CategoryTabs";
import Feed from "@/components/Feed";
import type { Category, Story } from "@/lib/types";

export default function HomeClient({ stories }: { stories: Story[] }) {
  const sp = useSearchParams();
  const cat = (sp.get("cat") as Category) || "All";

  const filtered = useMemo(
    () => (cat === "All" ? stories : stories.filter((s) => s.category === cat)),
    [stories, cat]
  );

  return (
    <>
      <CategoryTabs active={cat} />
      <div className="mt-4">
        <Feed stories={filtered} />
      </div>
    </>
  );
}
