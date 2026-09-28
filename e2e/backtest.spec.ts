import { test, expect } from '@playwright/test';
import { setLoginInfo, defaultMocks } from './helpers';

test.describe('Backtesting', () => {
  test.beforeEach(async ({ page }) => {
    await defaultMocks(page);
    page.route('**/api/v1/show_config', (route) => {
      return route.fulfill({ path: `./e2e/testData/backtest/show_config_webserver.json` });
    });
    page.route('**/api/v1/strategies', (route) => {
      return route.fulfill({ path: `./e2e/testData/backtest/strategies.json` });
    });

    await page.route('**/api/v1/backtest', (route) => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          path: './e2e/testData/backtest/backtest_post_start.json',
        });
      } else if (route.request().method() === 'GET') {
        route.fulfill({
          path: './e2e/testData/backtest/backtest_get_end.json',
        });
      }
    });

    await setLoginInfo(page);
  });
  test('Starts webserver mode', async ({ page }) => {
    await page.goto('/backtest');

    await expect(page.getByRole('heading', { name: 'Backtesting', level: 1 })).toBeInViewport();
    // The Backtest link sits in the collapsible "Engine tools" sidebar group.
    const sidebar = page.getByRole('navigation', { name: 'Main' });
    await sidebar.getByRole('button', { name: 'Engine tools' }).click();
    const backtestLink = sidebar.getByRole('link', { name: 'Backtest' });
    await expect(backtestLink).toBeInViewport();
    await expect(backtestLink).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('tab', { name: 'Run backtest' })).toBeInViewport();
    await expect(page.getByRole('heading', { name: 'Strategy', exact: true })).toBeInViewport();
    const useTime = page.getByRole('checkbox', { name: 'Use time' });
    await expect(useTime).toBeVisible();
    await useTime.scrollIntoViewIfNeeded();
    await expect(useTime).toBeInViewport();

    const strategySelect = page.locator('#strategy-select');
    await expect(strategySelect).toBeVisible();
    await strategySelect.scrollIntoViewIfNeeded();
    await expect(strategySelect).toBeInViewport();
    await page.locator('#strategy-select svg').click();
    await page.getByRole('option', { name: 'SampleStrategy' }).click();

    const option = page.locator('[id="strategy-select"]');
    await expect(option).toBeAttached();
    const analyzeButton = page.getByRole('tab', { name: 'Analyze result' });
    await expect(analyzeButton).toBeDisabled();

    const startBacktestButton = page.getByRole('button', { name: 'Start backtest' });
    await Promise.all([startBacktestButton.click(), page.waitForResponse('**/api/v1/backtest')]);

    // All buttons are now enabled
    await expect(analyzeButton).toBeEnabled();
  });
});
