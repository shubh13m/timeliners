import type { Metadata } from "next";
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
    default: "Timeliner — Indian News as Interactive Timelines",
    template: "%s · Timeliner",
  },
  description:
    "Top Indian news transformed into chronological, interactive story timelines. Auto-updated 3× daily.",
  applicationName: "Timeliner",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    type: "website",
    siteName: "Timeliner",
    images: ["/og-default.png"],
  },
  twitter: { card: "summary_large_image", images: ["/og-default.png"] },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-[#0a0a0a] text-gray-100">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(siteJsonLd()) }}
        />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
