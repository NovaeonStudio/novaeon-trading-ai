import { test, expect } from '@playwright/test';
import { setLoginInfo, defaultMocks } from './helpers';

test.describe('Chart', () => {
  test.beforeEach(async ({ page }) => {
    await defaultMocks(page);
    // The Markets page (successor of /graph) also lists per-pair performance.
    page.route('**/api/v1/performance', (route) =>
      route.fulfill({ path: './e2e/testData/performance.json' }),
    );
    await setLoginInfo(page);
  });
  test('Chart page', async ({ page }) => {
    await Promise.all([
      page.goto('/graph'),
      page.waitForResponse('**/whitelist'),
      page.waitForResponse('**/blacklist'),
      page.waitForResponse('**/pair_candles'),
    ]);

    // The legacy /graph page forwards to Markets.
    await expect(page).toHaveURL(/\/markets$/);

    await page.getByRole('button', { name: 'Refresh chart' }).click();
    // await page.click('input[title="AutoRefresh"]');

    await expect(page.getByText('NoActionStrategyFut · 1m', { exact: true })).toBeVisible();
    const heikinAshiCheck = page.getByRole('checkbox', { name: 'Heikin Ashi' });
    await heikinAshiCheck.click();
    await expect(heikinAshiCheck).toBeChecked();

    // Reload triggers a new request
    await Promise.all([
      page.getByRole('button', { name: 'Refresh chart' }).click(),

      page.waitForResponse('**/pair_candles'),
    ]);
    // Disable Heikin Ashi
    await heikinAshiCheck.click();
    await expect(heikinAshiCheck).not.toBeChecked();
    // Default plotconfig exists

    await expect(page.locator('#plotConfigSelect')).toHaveText('default');
  });

  test('Plot configurator', async ({ page }) => {
    await Promise.all([
      page.goto('/graph'),
      page.waitForResponse('**/whitelist'),
      page.waitForResponse('**/blacklist'),
      page.waitForResponse('**/pair_candles'),
    ]);

    // Wait for the chart to load
    await expect(page.getByText('NoActionStrategyFut · 1m', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Plot configurator' }).click();
    await page.getByRole('button', { name: 'From template' }).click();
    // Apply bollinger bands

    await page.getByRole('option', { name: 'BollingerBands' }).click();

    // await page.getByLabel('Select Templates').selectOption('BollingerBands');
    // Select template - Try to use
    await page.getByRole('button', { name: 'Use Template' }).click();
    // Accept remapping and close
    await page.getByRole('button', { name: 'Apply Template' }).click();
    await page.getByRole('button', { name: 'Save' }).click();

    const indicatorPanel = page.getByText('Indicators in this plotb');

    const options = await indicatorPanel.getByRole('option').allTextContents();
    await expect(options).toContain('bb_lowerband');
    await expect(options).toStrictEqual(['bb_upperband', 'bb_lowerband']);

    // indicatorPanel.selectOption('bb_lowerband');
    // Close Plot configurator
    await page.getByRole('button', { name: 'Close' }).click();

    await expect(page.locator('canvas')).toHaveScreenshot(
      'Chart-Plot-with_BollingerBands-Dark.png',
      {
        threshold: 0.15,
        maxDiffPixelRatio: 0.15,
      },
    );

    await page.getByRole('button', { name: 'Switch to light theme' }).click();

    await expect(page.locator('canvas')).toHaveScreenshot('Chart-Plot-with_BollingerBands.png', {
      threshold: 0.15,
      maxDiffPixelRatio: 0.15,
    });
    // Should assert if indicators have been set
    // but it's a canvas ...
  });
});
