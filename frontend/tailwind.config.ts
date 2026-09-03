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
      // Token shell (nilai nyata di index.css via CSS variables).
      colors: {
        surface: {
          bg: "var(--bg)",
          elevated: "var(--bg-elevated)",
          sidebar: "var(--sidebar)",
          hover: "var(--hover)",
          border: "var(--border)",
          text: "var(--text)",
          muted: "var(--text-muted)",
          accent: "var(--accent)",
        },
      },
      borderRadius: {
        DEFAULT: "5px",
      },
    },
  },
  plugins: [],
} satisfies Config;
