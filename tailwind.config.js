/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          green:  '#00e676',
          amber:  '#ffab00',
          red:    '#ff1744',
          purple: '#7c6af7',
          dark:   '#0d1117',
        },
        surface: '#111118',
        surface2: '#1a1a24',
        border: 'rgba(255,255,255,0.07)',
        text: {
          primary: '#f0f0f5',
          muted: '#6b6b80',
        }
      },
      fontFamily: {
        sans:    ['DM Sans', 'system-ui', 'sans-serif'],
        display: ['Syne', 'sans-serif'],
        mono:    ['DM Mono', 'monospace'],
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
  ]
}
