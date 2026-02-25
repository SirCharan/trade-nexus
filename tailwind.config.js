/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        depth: '#030303',
        surface: '#0a0a0a',
        panel: '#0f0f0f',
        elevated: '#141414',
        'accent-red': '#eb3b3b',
        'accent-green': '#22c55e',
        'accent-blue': '#3b82f6',
        'border-subtle': '#1a1a1a',
        'border-medium': '#252525',
        'text-primary': '#e8e8e8',
        'text-secondary': '#888888',
        'text-muted': '#555555',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
