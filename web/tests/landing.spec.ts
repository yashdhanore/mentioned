import { expect, test } from '@playwright/test';

const requiredCopy = [
  'Save the books inside Reels.',
  'A recommendation passes by once.',
  'Share the source. Keep the trail.',
  'Finding books...',
  'Books mentioned',
  'The post is still saved.',
  'Never lose the book recommendation again.'
];

test('renders the landing story and primary sections', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('banner')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Save the books inside Reels.');

  for (const copy of requiredCopy) {
    await expect(page.getByText(copy, { exact: false }).first()).toBeAttached();
  }

  await expect(page.locator('#story')).toBeVisible();
  await expect(page.locator('#shelf')).toBeVisible();
  await expect(page.locator('#reader-memory')).toBeVisible();
  await expect(page.locator('#final-cta')).toBeVisible();
});

test('primary CTA scroll target is present and reachable', async ({ page }) => {
  await page.goto('/');

  const cta = page.getByRole('link', { name: /See how it works/i }).first();
  await expect(cta).toBeVisible();
  await expect(cta).toHaveAttribute('href', '#story');

  await cta.click();
  await expect(page.locator('#story')).toBeInViewport();
});

test('mobile layout has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  const hasNoHorizontalOverflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1;
  });

  expect(hasNoHorizontalOverflow).toBe(true);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.locator('.hero-collage')).toBeVisible();
});

test('reduced motion uses the non-pinned story path', async ({ browser }) => {
  const context = await browser.newContext({
    reducedMotion: 'reduce',
    viewport: { width: 1440, height: 1000 }
  });
  const page = await context.newPage();

  await page.goto('/');
  await page.waitForFunction(() => document.documentElement.dataset.motion === 'reduced');

  await expect(page.locator('html')).toHaveAttribute('data-motion', 'reduced');
  await expect(page.locator('#shelf')).toBeVisible();

  await context.close();
});
