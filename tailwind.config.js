/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./frontend/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#bbc7df',
        'on-primary': '#253144',
        'primary-container': '#0a1628',
        'on-primary-container': '#758096',
        'secondary': '#ffb598',
        'on-secondary': '#591d00',
        'secondary-container': '#b94501',
        'on-secondary-container': '#ffe7df',
        'tertiary': '#ffb59d',
        'on-tertiary': '#5d1800',
        'background': '#0a1628',
        'surface': '#111415',
        'surface-container': '#1d2021',
        'surface-container-high': '#282a2b',
        'surface-container-highest': '#323536',
        'surface-container-lowest': '#0c0f10',
        'outline': '#8f9097',
        'outline-variant': '#45474c',
        'on-surface': '#e1e3e4',
        'on-surface-variant': '#c5c6cd',
        'navy-mid': '#142240',
        'navy-light': '#1e3460',
        'orange-glow': '#D56434',
        'interactive-red': 'rgba(255, 0, 0, 0.7)',
        'emerald': {
          300: '#6ee7b7',
          500: '#10b981',
        },
      },
      fontFamily: {
        'serif': ['Playfair Display', 'Georgia', 'serif'],
        'sans': ['Source Sans 3', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        'mono': ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in',
        'spin': 'spin 1s linear infinite',
        'shimmer': 'shimmer 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
