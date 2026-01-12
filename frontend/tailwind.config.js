module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        gray: {
          950: '#0a0e27',
        }
      },
      fontFamily: {
        mono: ['Monaco', 'Courier New', 'monospace'],
      }
    },
  },
  plugins: [],
}
