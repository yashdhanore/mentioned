import { defineConfig } from 'astro/config';

import sitemap from '@astrojs/sitemap';

// The production web origin (render.yaml's mentioned-web service, see docs/deployment.md);
// PUBLIC_SITE_URL lets a preview/staging build or custom domain override it.
const SITE_URL = process.env.PUBLIC_SITE_URL || 'https://mentioned-web.onrender.com';

export default defineConfig({
  site: SITE_URL,
  output: 'static',
  integrations: [sitemap()],
});