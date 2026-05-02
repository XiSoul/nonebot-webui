import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    outDir: '../nb_cli_plugin_webui/dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return

          if (id.includes('monaco-editor')) return 'monaco'
          if (id.includes('echarts') || id.includes('vue-echarts')) return 'charts'
          if (id.includes('@vue') || id.includes('/vue/') || id.includes('vue-router') || id.includes('pinia')) {
            return 'vue-vendor'
          }
          if (id.includes('material-symbols')) return 'icons'

          return 'vendor'
        }
      }
    }
  }
})
