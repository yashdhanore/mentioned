import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const outputDir = join(root, 'test-results', 'screenshots');
mkdirSync(outputDir, { recursive: true });

const checkpoints = [
  { name: 'hero', y: 0 },
  { name: 'story', selector: '#story' },
  { name: 'shelf', selector: '#shelf' },
  { name: 'waitlist', selector: '#waitlist' },
  { name: 'final-cta', selector: '#final-cta' }
];

const viewports = [
  { name: 'desktop', width: 1440, height: 1000, reducedMotion: 'no-preference' },
  { name: 'mobile', width: 390, height: 844, reducedMotion: 'no-preference' },
  { name: 'desktop-reduced-motion', width: 1440, height: 1000, reducedMotion: 'reduce' }
];

const browser = await chromium.launch();

for (const viewport of viewports) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    reducedMotion: viewport.reducedMotion
  });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4321/', { waitUntil: 'networkidle' });

  for (const checkpoint of checkpoints) {
    if (checkpoint.selector) {
      const targetTop = await page.locator(checkpoint.selector).evaluate((element) => {
        return element.getBoundingClientRect().top + window.scrollY;
      });
      await page.evaluate((y) => window.scrollTo({ top: Math.max(y - 118, 0), behavior: 'instant' }), targetTop);
    } else {
      await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'instant' }), checkpoint.y);
    }

    await page.screenshot({
      path: join(outputDir, `${viewport.name}-${checkpoint.name}.png`),
      fullPage: false
    });
  }

  await context.close();
}

await browser.close();
console.log(`screenshots written to ${outputDir}`);
