import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';

// Single-file build (`npm run build:single`): the whole app — JS, CSS, fonts
// and images — inlined into one self-contained dist-single/index.html that can
// be hosted anywhere static HTML is served (e.g. the SAS content server).
// Point it at a backend by editing the window.LENS_BACKEND block near the top
// of the emitted file.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: 'dist-single',
    assetsInlineLimit: 100_000_000,
    chunkSizeWarningLimit: 100_000,
  },
});
