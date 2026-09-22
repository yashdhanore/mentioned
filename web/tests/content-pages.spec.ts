import { expect, test } from '@playwright/test';

test('footer links to the privacy and support pages', async ({ page }) => {
  await page.goto('/');

  const privacyLink = page.getByRole('contentinfo').getByRole('link', { name: 'Privacy' });
  const supportLink = page.getByRole('contentinfo').getByRole('link', { name: 'Support' });

  await expect(privacyLink).toHaveAttribute('href', '/privacy');
  await expect(supportLink).toHaveAttribute('href', '/support');
});

test('privacy page renders with a heading and a link back home', async ({ page }) => {
  await page.goto('/privacy');

  await expect(page.getByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Back to home' })).toHaveAttribute('href', '/');
});

test('support page renders with a heading and a link to the privacy page', async ({ page }) => {
  await page.goto('/support');

  await expect(page.getByRole('heading', { level: 1, name: 'Support' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute(
    'href',
    '/privacy',
  );
});
