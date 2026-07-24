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
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Link href="/" className="text-lg font-bold tracking-tight text-white">
            <span className="text-blue-400">T</span>imelined
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
      </header>
      <main className="flex-1 pb-20">{children}</main>
      <footer className="border-t border-white/10 py-4 text-center text-xs text-gray-500">
        Timelined · Auto-generated from Indian news sources
      </footer>
    </div>
  );
}
