/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "JetBrains Mono",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        nexus: {
          950: "#05070e",
          900: "#0a0f1c",
          850: "#0d1424",
          800: "#111a2e",
          700: "#1b2740",
          600: "#27365a",
          500: "#3b4f7e",
          accent: "#6366f1",
          "accent-soft": "#818cf8",
        },
      },
    },
  },
  plugins: [],
};
