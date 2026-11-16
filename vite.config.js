import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 8765,
    host: "127.0.0.1",
  },
  build: {
    target: "es2022",
  },
});
