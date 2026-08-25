import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      // Token Notion-style (nilai nyata di index.css via CSS variables).
      colors: {
        notion: {
          bg: "var(--n-bg)",
          elevated: "var(--n-bg-elevated)",
          sidebar: "var(--n-sidebar)",
          hover: "var(--n-hover)",
          border: "var(--n-border)",
          text: "var(--n-text)",
          muted: "var(--n-text-muted)",
          accent: "var(--n-accent)",
        },
      },
      borderRadius: {
        DEFAULT: "5px",
      },
    },
  },
  plugins: [],
} satisfies Config;
