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
          green:     '#25D366', // WhatsApp green
          greenDark: '#128C7E',
          greenLight:'#4FCE5D',
          greenGlow: 'rgba(37,211,102,0.15)',
          amber:     '#FFB300',
          red:       '#FF1744',
          purple:    '#25D366', // removed purple
          dark:      '#050505',
        },
        surface:  '#FFFFFF',
        surface2: '#F0F2F5', // WhatsApp web background
        surface3: '#E9EDF0',
        surface4: '#D1D7DB',
        border:   'rgba(0,0,0,0.1)',
        text: {
          primary: '#000000',
          muted:   '#333333',
        }
      },
      fontFamily: {
        sans:    ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
        display: ['Syne', 'sans-serif'],
        mono:    ['DM Mono', 'monospace'],
      },
      borderRadius: {
        xl:   '0.75rem',
        '2xl':'1rem',
        '3xl':'1.5rem',
        '4xl':'2rem',
      },
      boxShadow: {
        'glow-green': '0 0 30px rgba(37,211,102,0.15), 0 0 60px rgba(37,211,102,0.05)',
        'glow-green-sm': '0 0 15px rgba(37,211,102,0.12)',
        'glow-amber': '0 0 30px rgba(255,179,0,0.12)',
        'glow-red':   '0 0 20px rgba(255,23,68,0.15)',
        'card':       '0 4px 24px rgba(0,0,0,0.4)',
        'card-hover': '0 8px 40px rgba(0,0,0,0.6)',
        'glass':      'inset 0 1px 0 rgba(255,255,255,0.04)',
      },
      animation: {
        'float':     'float 6s ease-in-out infinite',
        'pulse-glow':'pulseGlow 3s ease-in-out infinite',
        'slide-up':  'slideUp 0.4s cubic-bezier(0.16,1,0.3,1)',
        'fade-in':   'fadeIn 0.3s ease-out both',
        'scale-in':  'scaleIn 0.3s cubic-bezier(0.16,1,0.3,1) both',
        'shake':     'shake 0.5s cubic-bezier(.36,.07,.19,.97) both',
        'shimmer':   'shimmer 2s linear infinite',
        'bounce-sm': 'bounceSm 0.3s cubic-bezier(0.34,1.56,0.64,1)',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-20px)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '0.4' },
          '50%':      { opacity: '0.8' },
        },
        slideUp: {
          '0%':   { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%':   { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%':   { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        shake: {
          '0%, 100%':          { transform: 'translateX(0)' },
          '10%, 30%, 50%, 70%, 90%': { transform: 'translateX(-5px)' },
          '20%, 40%, 60%, 80%':      { transform: 'translateX(5px)' },
        },
        shimmer: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        bounceSm: {
          '0%':   { transform: 'scale(0.9)' },
          '50%':  { transform: 'scale(1.05)' },
          '100%': { transform: 'scale(1)' },
        },
      },
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
  ]
}
