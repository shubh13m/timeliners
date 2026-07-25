import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Timelined",
    short_name: "Timelined",
    description: "Indian news as interactive timelines",
    start_url: "/",
    display: "standalone",
    // Splash background — kept dark so the app doesn't flash white before boot.
    background_color: "#0a0a0a",
    // Address-bar / task-switcher / install-popup accent. Matches the in-app
    // red used across category pills, timeline dots, and links.
    theme_color: "#dc2626",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // A maskable icon lets Android crop to its adaptive-icon shape (circle,
      // squircle, etc.) without cutting off the logo. Reuses the 512 asset;
      // if the source image has enough padding it'll look correct in the
      // "safe zone". Otherwise regenerate this from the design instructions
      // in the reply below.
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
      { src: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
