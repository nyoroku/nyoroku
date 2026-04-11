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
        primary:   '#2d545e',   /* Night Blue */
        'primary-dark': '#12343b', /* Night Blue Shadow */
        accent:    '#e1b382',   /* Sand Tan */
        'accent-dark': '#c89666', /* Sand Tan Shadow */
        success:   '#16A34A',
        warning:   '#F59E0B',
        danger:    '#DC2626',
        'bg-main':    '#F8F9FB',
        'bg-surface': '#FFFFFF',
        border:    '#E5E7EB',
        'text-primary':   '#12343b',
        'text-secondary': '#6B7280',
        'cart-bg':    '#F1F5F9',
        'selected-item': '#e1b38233',
        hover:     '#F3F4F6',
        disabled:  '#D1D5DB',
      },
      fontFamily: {
        sans:  ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono:  ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'xs':  ['12px', { lineHeight: '16px' }],
        'sm':  ['14px', { lineHeight: '20px' }],
        'base':['16px', { lineHeight: '24px' }],
        'lg':  ['18px', { lineHeight: '28px' }],
        'xl':  ['20px', { lineHeight: '28px' }],
        '2xl': ['24px', { lineHeight: '32px' }],
        '3xl': ['30px', { lineHeight: '36px' }],
      },
      borderRadius: {
        xl:   '0.75rem',
        '2xl':'1rem',
        '3xl':'1.5rem',
      },
      boxShadow: {
        'card':   '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
        'card-lg':'0 4px 12px rgba(0,0,0,0.08)',
        'modal':  '0 20px 60px rgba(0,0,0,0.15)',
      },
      animation: {
        'fade-in':  'fadeIn 0.2s ease-out both',
        'slide-up': 'slideUp 0.3s cubic-bezier(0.16,1,0.3,1)',
        'scale-in': 'scaleIn 0.2s cubic-bezier(0.16,1,0.3,1) both',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%':   { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%':   { transform: 'scale(0.96)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
  ]
}
