/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'system-ui', 'sans-serif'],
        serif: ['DM Serif Display', 'serif'],
      },
      colors: {
        coral: { DEFAULT: '#D86C52', light: '#E8927A', dark: '#C25A3E' },
        sage: { DEFAULT: '#6BA08A', light: '#8FBFAB' },
        teal: { DEFAULT: '#4E8C96', light: '#6AABB5' },
        mustard: { DEFAULT: '#DAB04E', light: '#E8C872' },
        'dusty-pink': '#C3787E',
        plum: '#8C5A82',
        cream: '#FAF5ED',
        'warm-bg': '#F5EDE0',
        'warm-card': '#FFFAF3',
        'warm-brown': '#78503C',
        'text-dark': '#3D2B1F',
        'text-mid': '#6B5344',
        'text-light': '#9A8678',
        border: '#E8DDD0',
      },
      borderRadius: {
        'card': '20px',
        'stat': '18px',
      },
      boxShadow: {
        'warm': '0 4px 16px rgba(60, 40, 20, 0.08)',
        'warm-md': '0 8px 28px rgba(60, 40, 20, 0.12)',
        'warm-lg': '0 8px 30px rgba(107, 160, 138, 0.25)',
      },
    },
  },
  plugins: [],
};
