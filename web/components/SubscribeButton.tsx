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

  // Icon-only button. Reclaims header space for a bigger logo while still
  // exposing state via color, title, and disabled attribute.
  const icon =
    state === "granted" ? "🔔" : state === "denied" ? "🔕" : state === "loading" ? "…" : "🔔";
  const title =
    state === "granted"
      ? "Subscribed to updates"
      : state === "denied"
      ? "Notifications blocked"
      : state === "loading"
      ? "Subscribing…"
      : "Get updates";

  return (
    <button
      onClick={onClick}
      disabled={state === "loading" || state === "granted"}
      title={title}
      aria-label={title}
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 text-base transition hover:bg-white/10 disabled:opacity-70 ${
        state === "granted"
          ? "bg-red-600/20 text-red-300"
          : state === "denied"
          ? "bg-white/5 text-gray-500"
          : "bg-white/5 text-gray-200"
      }`}
    >
      {icon}
    </button>
  );
}
