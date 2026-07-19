import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Borrowed deliberately from GitHub's own diff/UI language, since
        // this product's job is literally auditing GitHub evidence.
        canvas: "#0D1117",
        surface: "#161B22",
        border: "#30363D",
        ink: "#E6EDF3",
        muted: "#7D8590",
        evidenced: "#3FB950", // GitHub's diff-add green
        gap: "#F85149",      // GitHub's diff-remove red
        accent: "#58A6FF",   // GitHub's link blue
        unverified: "#D29922", // GitHub's own "attention" amber - neither pass nor fail
      },
      fontFamily: {
        mono: ["var(--font-plex-mono)", "monospace"],
        sans: ["var(--font-plex-sans)", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
