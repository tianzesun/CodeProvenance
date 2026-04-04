/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          200: '#b9dffd',
          300: '#7cc7fb',
          400: '#36aaf6',
          500: '#0c8ee9',
          600: '#006fc5',
          700: '#0058a1',
          800: '#004b85',
          900: '#003f6f',
          950: '#00284b',
        },
        slate: {
          850: '#151f32',
          900: '#0f172a',
          950: '#020617',
        },
      },
    },
  },
  plugins: [],
};
