import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#8B1E3F",
          hover: "#731734",
          foreground: "#FFFFFF",
          muted: "#F5EBEF",
        },
        accent: {
          DEFAULT: "#C89B3C",
          foreground: "#FFFFFF",
        },
        surface: {
          DEFAULT: "#F8F9FB",
          card: "#FFFFFF",
        },
        rail: {
          ink: "#1E293B",
          muted: "#64748B",
          line: "#E8ECF2",
          panel: "#F8F9FB",
          soft: "#F1F3F7",
        },
        success: {
          DEFAULT: "#22C55E",
          muted: "#ECFDF3",
        },
        warning: {
          DEFAULT: "#F59E0B",
          muted: "#FFFBEB",
        },
        error: {
          DEFAULT: "#DC2626",
          muted: "#FEF2F2",
        },
      },
      borderRadius: {
        "2xl": "16px",
        xl: "14px",
        lg: "12px",
        md: "8px",
        sm: "6px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15, 23, 42, 0.04)",
        card: "0 1px 3px rgba(15, 23, 42, 0.05), 0 4px 16px rgba(15, 23, 42, 0.04)",
        premium: "0 4px 24px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.04)",
        float: "0 8px 32px rgba(15, 23, 42, 0.08), 0 2px 8px rgba(15, 23, 42, 0.04)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
      transitionDuration: {
        DEFAULT: "200ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
