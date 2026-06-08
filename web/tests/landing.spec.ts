import { expect, test } from '@playwright/test';

const requiredCopy = [
  'Turn BookTok into your reading list.',
  'FROM THE REEL',
  'A short list of books I keep coming back to.',
  'How a Reel becomes a reading list.',
  'Send it to Mentioned.',
  'Mentioned looks for books.',
  'Your list gets updated.',
  'No clear title?',
  'The post stays with the books.',
  'Mentioned pulls the book rec out of the Reel',
  'Join the BookTok-to-TBR waitlist.',
  'Get the iOS share-sheet build first.',
  'Save your first Reel when invites open.',
  'Never lose a book rec in the feed again.'
];

test('renders the landing story and primary sections', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('banner')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Turn BookTok into your reading list.');

  for (const copy of requiredCopy) {
    await expect(page.getByText(copy, { exact: false }).first()).toBeAttached();
  }

  await expect(page.locator('#story')).toBeVisible();
  await expect(page.locator('#shelf')).toBeVisible();
  await expect(page.locator('#waitlist')).toBeVisible();
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

test('desktop hero keeps subtext and CTAs in the first viewport', async ({ page }) => {
  await page.setViewportSize({ width: 921, height: 909 });
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.locator('.hero-section__copy p')).toBeVisible();
  await expect(page.locator('.hero-section__actions')).toBeVisible();

  const heroFit = await page.evaluate(() => {
    const actions = document.querySelector('.hero-section__actions')?.getBoundingClientRect();
    const subtext = document.querySelector('.hero-section__copy p')?.getBoundingClientRect();

    return Boolean(
      actions &&
        subtext &&
        subtext.bottom <= window.innerHeight &&
        actions.bottom <= window.innerHeight
    );
  });

  expect(heroFit).toBe(true);
});

test('desktop workflow cards remain separated and readable', async ({ page }) => {
  await page.setViewportSize({ width: 1567, height: 969 });
  await page.goto('/');
  await page.locator('#story').scrollIntoViewIfNeeded();
  await page.waitForTimeout(850);

  const overlaps = await page.locator('.workflow-stage [data-story-card]').evaluateAll((cards) => {
    const rects = cards.map((card, index) => {
      const rect = card.getBoundingClientRect();
      return {
        index,
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom
      };
    });

    const overlappingPairs: string[] = [];

    for (let first = 0; first < rects.length; first += 1) {
      for (let second = first + 1; second < rects.length; second += 1) {
        const a = rects[first];
        const b = rects[second];
        const horizontalOverlap = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const verticalOverlap = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);

        if (horizontalOverlap > 2 && verticalOverlap > 2) {
          overlappingPairs.push(`${a.index}-${b.index}`);
        }
      }
    }

    return overlappingPairs;
  });

  expect(overlaps).toEqual([]);
});

test('desktop shelf section keeps the saved list and Reel note readable', async ({ page }) => {
  await page.setViewportSize({ width: 1567, height: 969 });
  await page.goto('/');
  await page.locator('#shelf').scrollIntoViewIfNeeded();
  await page.waitForTimeout(850);

  await expect(page.getByRole('heading', { name: 'The post stays with the books.' })).toBeVisible();
  await expect(page.locator('[data-shelf-phone]')).toBeVisible();
  await expect(page.locator('[data-shelf-memory]')).toBeVisible();

  const keyElementsAreInViewport = await page.evaluate(() => {
    const phone = document.querySelector('[data-shelf-phone]')?.getBoundingClientRect();
    const memory = document.querySelector('[data-shelf-memory]')?.getBoundingClientRect();

    if (!phone || !memory) {
      return false;
    }

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    return [phone, memory].every((rect) => {
      return rect.width > 0 &&
        rect.height > 0 &&
        rect.left >= 0 &&
        rect.top >= 0 &&
        rect.right <= viewportWidth &&
        rect.bottom <= viewportHeight;
    });
  });

  expect(keyElementsAreInViewport).toBe(true);
});

test('waitlist form posts signup feedback', async ({ page }) => {
  await page.route('**/v1/waitlist', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        id: '00000000-0000-4000-8000-000000000099',
        email: 'reader@example.com',
        created: true,
        created_at: '2026-06-08T00:00:00Z'
      })
    });
  });

  await page.goto('/');
  await page.locator('#waitlist').scrollIntoViewIfNeeded();

  await page.getByLabel('Email').fill('reader@example.com');
  await page.getByRole('button', { name: /Join waitlist/i }).click();

  await expect(page.locator('[data-waitlist-status]')).toContainText("You're on the waitlist");

  const storedEmail = await page.evaluate(() => window.localStorage.getItem('mentioned.waitlist.email'));
  expect(storedEmail).toBe('reader@example.com');
});

test('reduced motion shows the landing page without pinned story animation', async ({ browser }) => {
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
