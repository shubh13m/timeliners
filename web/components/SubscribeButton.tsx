"use client";

import { useEffect, useState } from "react";
import { currentPermission, isPushSupported, subscribeToPush } from "@/lib/push";

export default function SubscribeButton() {
  const [supported, setSupported] = useState(false);
  const [state, setState] = useState<
    "idle" | "loading" | "granted" | "denied" | "unsupported"
  >("idle");

  useEffect(() => {
    (async () => {
      const ok = await isPushSupported();
      setSupported(ok);
      if (!ok) return setState("unsupported");
      const perm = await currentPermission();
      if (perm === "granted") setState("granted");
      else if (perm === "denied") setState("denied");
    })();
  }, []);

  if (!supported) return null;

  async function onClick() {
    setState("loading");
    const res = await subscribeToPush();
    setState(res.ok ? "granted" : "denied");
  }

  const label =
    state === "loading"
      ? "Subscribing…"
      : state === "granted"
      ? "🔔 Subscribed"
      : state === "denied"
      ? "🔕 Blocked"
      : "🔔 Get updates";

  return (
    <button
      onClick={onClick}
      disabled={state === "loading" || state === "granted"}
      className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-gray-200 transition hover:bg-white/10 disabled:opacity-70"
    >
      {label}
    </button>
  );
}
