"use client";

import { useEffect, Suspense } from "react";
import Link from "next/link";
import SearchBar from "./SearchBar";
import SubscribeButton from "./SubscribeButton";

export default function AppShell({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-black/60 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 pt-3">
          <Link
            href="/"
            aria-label="Timelined home"
            className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl"
          >
            <span className="text-red-500">T</span>imelined
          </Link>
          <div className="flex-1">
            <Suspense fallback={<div className="h-9" />}>
              <SearchBar />
            </Suspense>
          </div>
          <Link
            href="/archive/"
            className="hidden text-sm text-gray-300 hover:text-white sm:inline"
          >
            Archive
          </Link>
          <SubscribeButton />
        </div>
        {/* Tagline sits right under the header row so first-time visitors
            instantly understand what the site does. Kept small and muted
            so it doesn't compete with the logo/search. */}
        <p className="mx-auto max-w-6xl px-4 pb-2 pt-1 text-xs italic text-gray-400 sm:text-sm">
          Follow the story, not just the headline.
        </p>
      </header>
      <main className="flex-1 pb-20">{children}</main>
      <footer className="border-t border-white/10 py-4 text-center text-xs text-gray-500">
        Timelined · Auto-generated from Indian news sources
      </footer>
    </div>
  );
}
