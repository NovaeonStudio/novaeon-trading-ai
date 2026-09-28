import { test, expect } from '@playwright/test';
import { setLoginInfo, defaultMocks, tradeMocks } from './helpers';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await defaultMocks(page);
    await tradeMocks(page);
    await setLoginInfo(page);
  });
  test('Dashboard Page', async ({ page }) => {
    // The legacy /dashboard page forwards to the Command center.
    await Promise.all([
      page.goto('/dashboard'),
      page.waitForResponse('**/status'),
      page.waitForResponse('**/profit'),
      page.waitForResponse('**/balance'),
    ]);
    await expect(page).toHaveURL(/\/command$/);
    const main = page.getByRole('main');
    await expect(main.getByRole('heading', { name: 'Command center', level: 1 })).toBeVisible();
    for (const name of ['Equity', 'Risk', 'Edge']) {
      const heading = main.getByRole('heading', { name, exact: true });
      await expect(heading).toBeVisible();
      await expect(heading).toBeInViewport();
    }
    await expect(page.getByText('NoActionStrategy · 1m')).toBeVisible();

    const openPositions = main.getByRole('heading', { name: 'Open positions' });
    await openPositions.scrollIntoViewIfNeeded();
    await expect(openPositions).toBeInViewport();
    await expect(main.getByRole('heading', { name: 'Equity and drawdown' })).toBeVisible();
    await expect(main.getByRole('heading', { name: 'Pair leaderboard' })).toBeVisible();

    // Scroll to bottom
    const decisionLog = main.getByRole('heading', { name: 'Sentinel decision log' });
    await decisionLog.scrollIntoViewIfNeeded();
    await expect(decisionLog).toBeInViewport();
    const excursionMap = main.getByRole('heading', { name: 'Excursion map' });
    await excursionMap.scrollIntoViewIfNeeded();
    await expect(excursionMap).toBeInViewport();
    await expect(main.getByRole('heading', { name: 'Daily P&L' })).toBeVisible();
  });

  test('Dashboard Page - mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await Promise.all([
      page.goto('/dashboard'),
      page.waitForResponse('**/status'),
      page.waitForResponse('**/profit'),
      page.waitForResponse('**/balance'),
    ]);
    const main = page.getByRole('main');
    await expect(main.getByRole('heading', { name: 'Command center', level: 1 })).toBeVisible();
    await expect(main.getByRole('heading', { name: 'Risk', exact: true })).toBeVisible();

    const viewportWidth = page.viewportSize()?.width ?? 0;
    // Cards must not be wider than the screen - otherwise most columns
    // are rendered off-screen and are unreachable on a phone.
    const cardWidths = await main
      .locator('section')
      .evaluateAll((elements) => elements.map((el) => el.getBoundingClientRect().width));

    expect(cardWidths.length).toBeGreaterThan(0);
    for (const cardWidth of cardWidths) {
      expect(cardWidth).toBeLessThanOrEqual(viewportWidth);
    }
    const openPositions = main.getByRole('heading', { name: 'Open positions' });
    await expect(openPositions).toBeVisible();
    await openPositions.scrollIntoViewIfNeeded();
    await expect(openPositions).toBeInViewport();
  });
});
