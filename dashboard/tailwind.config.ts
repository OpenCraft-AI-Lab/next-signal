import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  // The design's CSS variables target `[data-theme="dark"]` selectors
  // (see globals.css). Wire Tailwind dark utilities to the same selector
  // so `dark:` and the design's `data-theme="dark"` switch together.
  darkMode: ["selector", "[data-theme='dark']"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-subtle": "var(--bg-subtle)",
        "bg-inset": "var(--bg-inset)",
        card: "var(--card)",
        elevated: "var(--elevated)",
        hover: "var(--hover)",
        "active-bg": "var(--active-bg)",
        text: "var(--text)",
        "text-2": "var(--text-2)",
        "text-3": "var(--text-3)",
        "text-4": "var(--text-4)",
        border: "var(--border)",
        "border-2": "var(--border-2)",
        "border-strong": "var(--border-strong)",
        line: "var(--line)",
        accent: "var(--accent)",
        "accent-hover": "var(--accent-hover)",
        "accent-tint": "var(--accent-tint)",
        "accent-text": "var(--accent-text)",
        "accent-fg": "var(--accent-fg)",
        green: "var(--green)",
        red: "var(--red)",
        amber: "var(--amber)",
        purple: "var(--purple)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        sm: "var(--r-1)",
        DEFAULT: "var(--r-3)",
        md: "var(--r-3)",
        lg: "var(--r-4)",
        xl: "var(--r-5)",
      },
      boxShadow: {
        ring: "var(--ring)",
        "ring-light": "var(--ring-light)",
        card: "var(--shadow-card)",
        pop: "var(--shadow-pop)",
        menu: "var(--shadow-menu)",
      },
    },
  },
  plugins: [animate],
};

export default config;
