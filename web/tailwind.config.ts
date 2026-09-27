import type { Config } from "tailwindcss"

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      colors: {
        ink: "#070b14",
        panel: "#101826",
        line: "#223044",
        mist: "#93a4bd",
        foam: "#e7eef8",
        tide: "#3ee0c5",
        amber: "#f5b942",
        flare: "#ff6b7d",
      },
    },
  },
  plugins: [],
}

export default config
