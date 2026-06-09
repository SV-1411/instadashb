/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Warm cream / beige / brown palette
        cream: "#FBF7F1",
        sand: "#EFE6D8",
        beige: "#E4D6C1",
        clay: "#C9A27E",
        mocha: "#9A7B5B",
        coffee: "#6F4E37",
        ink: "#3A2E25", // dark brown text
        pulse: "#A9764E", // warm accent (replaces the old blue)
      },
      boxShadow: {
        glass: "0 8px 32px rgba(111, 78, 55, 0.14)",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
