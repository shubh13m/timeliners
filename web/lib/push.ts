import { supabaseBrowser } from "./supabase";

const VAPID_PUBLIC = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function isPushSupported(): Promise<boolean> {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    !!VAPID_PUBLIC
  );
}

export async function currentPermission(): Promise<NotificationPermission | "unsupported"> {
  if (typeof Notification === "undefined") return "unsupported";
  return Notification.permission;
}

export async function subscribeToPush(): Promise<{ ok: boolean; error?: string }> {
  if (!(await isPushSupported())) return { ok: false, error: "unsupported" };
  if (!VAPID_PUBLIC) return { ok: false, error: "no VAPID key configured" };

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { ok: false, error: permission };

  const reg = await navigator.serviceWorker.ready;
  const keyBytes = urlBase64ToUint8Array(VAPID_PUBLIC);
  // Copy into a fresh ArrayBuffer to satisfy strict BufferSource typing
  const keyBuffer = new ArrayBuffer(keyBytes.byteLength);
  new Uint8Array(keyBuffer).set(keyBytes);
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: keyBuffer,
  });

  const json = sub.toJSON();
  const { error } = await supabaseBrowser()
    .from("push_subscriptions")
    .insert({
      endpoint: json.endpoint,
      p256dh: json.keys?.p256dh,
      auth: json.keys?.auth,
      user_agent: navigator.userAgent.slice(0, 200),
    });

  if (error && !error.message.toLowerCase().includes("duplicate")) {
    return { ok: false, error: error.message };
  }
  return { ok: true };
}
