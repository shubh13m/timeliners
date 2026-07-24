"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Feed from "@/components/Feed";
import { supabaseBrowser } from "@/lib/supabase";
import type { Story } from "@/lib/types";

function SearchInner() {
  const sp = useSearchParams();
  const q = sp.get("q") || "";
  const [results, setResults] = useState<Story[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!q) return;
    setLoading(true);
    supabaseBrowser()
      .rpc("search_stories", { q, lim: 30 })
      .then(({ data, error }) => {
        if (error) {
          console.error(error);
          setResults([]);
        } else {
          setResults((data as Story[]) || []);
        }
        setLoading(false);
      });
  }, [q]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="mb-4 text-2xl font-bold text-white">
        Search results {q && <span className="text-gray-400">· “{q}”</span>}
      </h1>
      {loading && <p className="text-gray-400">Searching…</p>}
      {!loading && q && results.length === 0 && (
        <p className="text-gray-400">No stories matched.</p>
      )}
      {!loading && !q && (
        <p className="text-gray-400">Type a query in the search bar above.</p>
      )}
      {results.length > 0 && <Feed stories={results} />}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-6 text-gray-400">Loading…</div>}>
      <SearchInner />
    </Suspense>
  );
}
