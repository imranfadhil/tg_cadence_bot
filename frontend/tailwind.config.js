/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'SF Pro Text', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        cadence: {
          canvas: '#FAFAFA',
          surface: '#FFFFFF',
          subtle: '#F4F4F5',
          border: '#E4E4E7',
          cobalt: '#2563EB',
        },
      },
      boxShadow: {
        micro: '0 1px 2px 0 rgba(24, 24, 27, 0.04)',
      },
    },
  },
  plugins: [],
};

