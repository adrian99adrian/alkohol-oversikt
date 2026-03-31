import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  base: "/alkohol-oversikt",
  outDir: "../docs",
  integrations: [tailwind()],
});
