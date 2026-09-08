import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { fileURLToPath, URL } from 'node:url';

// Single-file build (`npm run build:single`): the whole app — JS, CSS and
// fonts — inlined into one self-contained dist-single/index.html that can be
// hosted anywhere static HTML is served (e.g. the SAS content server).
// Brand images are NOT embedded: they load from the window.LENS_ASSETS URLs
// configured at the top of the emitted file (hosted alongside it, e.g. on
// SAS Viya), with typographic/gradient fallbacks when unset. Point the chat
// at a backend by editing the window.LENS_BACKEND block in the same place.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  resolve: {
    alias: {
      '@brand-assets': fileURLToPath(new URL('./src/assets-external.js', import.meta.url)),
    },
  },
  build: {
    outDir: 'dist-single',
    assetsInlineLimit: 100_000_000,
    chunkSizeWarningLimit: 100_000,
  },
});
