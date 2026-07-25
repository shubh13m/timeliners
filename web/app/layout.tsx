import type { Metadata } from "next";
import type { Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { siteJsonLd } from "@/lib/ld";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://timelined.pages.dev";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Timelined — Indian News as Interactive Timelines",
    template: "%s · Timelined",
  },
  description:
    "Top Indian news transformed into chronological, interactive story timelines. Auto-updated 3× daily.",
  applicationName: "Timelined",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    type: "website",
    siteName: "Timelined",
    images: ["/og-default.png"],
  },
  twitter: { card: "summary_large_image", images: ["/og-default.png"] },
};

// Tints the mobile browser address bar and Android status bar. Kept in sync
// with manifest.ts theme_color so the PWA install popup, launched app, and
// in-browser view all show the same red.
export const viewport: Viewport = {
  themeColor: "#dc2626",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-[#0a0a0a] text-gray-100">
        {/* Boot splash — rendered server-side so it appears on first paint,
            before React hydrates. Fades itself out via CSS animation
            (~1.8s total) so users have time to read the tagline. */}
        <div className="splash" aria-hidden="true">
          <div className="splash-inner">
            <div className="splash-brand">
              <span className="splash-brand-accent">T</span>imelined
            </div>
            <div className="splash-tagline">
              Follow the story, not just the headline.
            </div>
          </div>
        </div>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(siteJsonLd()) }}
        />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
