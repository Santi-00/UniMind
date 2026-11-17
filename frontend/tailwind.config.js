export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // In modalità scura "night" è semitrasparente: è la base dell'effetto vetro.
        night: { 950: "#070b1f", 900: "rgba(15,22,52,0.55)", 800: "rgba(255,255,255,0.07)", 700: "rgba(255,255,255,0.14)", 600: "rgba(255,255,255,0.22)" },
        brand: { 400: "#a78bfa", 500: "#8b5cf6", 600: "#7c3aed", 700: "#6d28d9" },
      },
      fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"] },
    },
  },
};
