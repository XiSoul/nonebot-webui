import daisyui from 'daisyui'
import themeConfig from './theme.config.cjs'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {}
  },
  plugins: [daisyui],
  daisyui: {
    themes: themeConfig.daisyThemes
  }
}
