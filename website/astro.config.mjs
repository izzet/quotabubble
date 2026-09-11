import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://izzet.github.io",
  base: "/quotabubble",
  integrations: [sitemap()],
});
