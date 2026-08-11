import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Toaster } from "sonner";

import { I18nProvider } from "@/components/i18n-provider";
import { Nav } from "@/components/nav";
import { ThemeProvider } from "@/components/theme-provider";
import { getLocale } from "@/lib/i18n/server";
import "./globals.css";

export const metadata: Metadata = {
  title: "next-signal · local dashboard",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // The nav only needs the UI-chrome locale (a cookie). Every other setting
  // moved to `/settings` and resolves there, so a page that is not the settings
  // page no longer reads four state files and a DB row to paint its header.
  const locale = await getLocale();
  // Geist exposes `--font-geist-sans` / `--font-geist-mono`; the design's
  // `--font-sans` / `--font-mono` resolve to those (see globals.css).
  return (
    <html
      lang={locale === "zh" ? "zh-CN" : "en"}
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body>
        <NuqsAdapter>
          <ThemeProvider>
            <I18nProvider locale={locale}>
              <div className="app">
                <Nav />
                <main>{children}</main>
              </div>
              <Toaster richColors position="bottom-right" />
            </I18nProvider>
          </ThemeProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
