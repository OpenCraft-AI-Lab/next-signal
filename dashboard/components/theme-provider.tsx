"use client";

import { ThemeProvider as NextThemeProvider } from "next-themes";
import type { ComponentProps } from "react";

// Wraps `next-themes` with the project's chosen attribute (`data-theme`) so
// the design's CSS variables (`[data-theme="dark"]` / `[data-theme="light"]`)
// swap together with Tailwind's `dark:` utilities (configured in
// tailwind.config.ts).
export function ThemeProvider({
  children,
  ...props
}: ComponentProps<typeof NextThemeProvider>) {
  return (
    <NextThemeProvider
      attribute="data-theme"
      defaultTheme="light"
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemeProvider>
  );
}
