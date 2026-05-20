import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";
import wasm from "vite-plugin-wasm";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "0.0.0.0",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_API_PROXY || "http://127.0.0.1",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  plugins: [wasm(), react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ['react', 'react-dom', 'styled-components'],
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify(mode),
    'process.env.MapboxAccessToken': JSON.stringify(''),
    'process.env.NODE_DEBUG': JSON.stringify(false),
  },
  build: {
    target: 'esnext',
    commonjsOptions: {
      include: [/node_modules/],
      transformMixedEsModules: true,
    },
  },
  optimizeDeps: {
    exclude: ['parquet-wasm'],
    include: [
      'buffer',
      'react',
      'react-dom',
      'react-redux',
      'redux',
      'styled-components',
      '@kepler.gl/components',
      '@kepler.gl/reducers',
      '@kepler.gl/actions',
      '@kepler.gl/constants',
      '@kepler.gl/utils',
      '@kepler.gl/processors',
      '@kepler.gl/schemas',
      '@kepler.gl/table',
      '@kepler.gl/layers',
      '@kepler.gl/deckgl-layers',
      '@kepler.gl/effects',
      '@kepler.gl/styles',
      '@kepler.gl/tasks',
    ],
    esbuildOptions: {
      target: 'es2020',
    },
  },
}));
