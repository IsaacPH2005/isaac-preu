import type { Config } from 'tailwindcss'

export default {
  content: [
    './components/**/*.{vue,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './composables/**/*.ts',
    './utils/**/*.ts',
    './app.vue',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'ui-serif', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        paper: {
          DEFAULT: '#f6f4ef',
          dark: '#ece8df',
        },
        ink: {
          DEFAULT: '#1c1b19',
          soft: '#4a4843',
          muted: '#8a867c',
        },
        accent: {
          50: '#eef6f3',
          100: '#d5ebe3',
          200: '#acd6c8',
          500: '#2f8a6f',
          600: '#1f6f58',
          700: '#185946',
        },
      },
      boxShadow: {
        card: '0 1px 0 rgba(28,27,25,0.04), 0 1px 3px rgba(28,27,25,0.06)',
        lift: '0 4px 24px -6px rgba(28,27,25,0.18)',
      },
      keyframes: {
        'slide-in': { from: { transform: 'translateX(100%)' }, to: { transform: 'translateX(0)' } },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
      },
      animation: {
        'slide-in': 'slide-in 220ms cubic-bezier(.2,.8,.2,1)',
        'fade-in': 'fade-in 160ms ease-out',
        shimmer: 'shimmer 1.4s infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
