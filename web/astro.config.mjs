import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/alkohol-oversikt",
  outDir: "../docs",
  vite: {
    plugins: [tailwindcss()],
  },
});
