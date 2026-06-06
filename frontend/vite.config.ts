/// <reference types="vitest/config" />

import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(root, "index.html"),
        movie: resolve(root, "movie.html"),
      },
    },
  },
  test: {
    environment: "happy-dom",
  },
});
