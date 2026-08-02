import type { Metadata } from "next";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "catchment-zone",
    template: "%s | catchment-zone",
  },
  description:
    "Search and compare UK schools, academy trusts, local authorities and published admissions catchment areas, using official government data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-GB">
      <body className="min-h-screen antialiased">
        <a
          href="#main-content"
          className="sr-only-focusable bg-background text-foreground fixed left-2 top-2 z-50 rounded-md border px-3 py-2"
        >
          Skip to main content
        </a>
        <SiteHeader />
        <main id="main-content" className="mx-auto max-w-6xl px-4 py-8">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
