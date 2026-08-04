import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Toaster } from "sonner";

import { I18nProvider } from "@/components/i18n-provider";
import { Nav } from "@/components/nav";
import { ThemeProvider } from "@/components/theme-provider";
import { getContentLanguage } from "@/lib/actions/language";
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
  // Both settings resolve on the server so the nav paints its actual state on
  // first render. They are independent: `locale` is UI chrome (cookie),
  // `contentLanguage` is what the pipeline generates in (state file).
  const [locale, contentLanguage] = await Promise.all([getLocale(), getContentLanguage()]);
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
                <Nav contentLanguage={contentLanguage} />
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
