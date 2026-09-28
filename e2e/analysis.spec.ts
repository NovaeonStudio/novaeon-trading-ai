import { test, expect } from '@playwright/test';
import { setLoginInfo, defaultMocks } from './helpers';

test.describe('Analysis', () => {
  test.beforeEach(async ({ page }) => {
    await defaultMocks(page);
    page.route('**/api/v1/show_config', (route) => {
      return route.fulfill({ path: `./e2e/testData/backtest/show_config_webserver.json` });
    });
    page.route('**/api/v1/strategies', (route) => {
      return route.fulfill({ path: `./e2e/testData/backtest/strategies.json` });
    });

    await setLoginInfo(page);
  });
  test('Analysis navigation', async ({ page }) => {
    await page.goto('/');
    const sidebar = page.getByRole('navigation', { name: 'Main' });
    // Analysis tools live in the collapsible "Engine tools" sidebar group.
    const engineToolsButton = sidebar.getByRole('button', { name: 'Engine tools' });
    const recursiveLink = sidebar.getByRole('link', { name: 'Recursive analysis' });
    const lookaheadLink = sidebar.getByRole('link', { name: 'Lookahead analysis' });
    await expect(engineToolsButton).toBeInViewport();
    await expect(engineToolsButton).toHaveAttribute('aria-expanded', 'false');
    await expect(recursiveLink).not.toBeInViewport();
    await expect(lookaheadLink).not.toBeInViewport();
    await engineToolsButton.click();
    await expect(engineToolsButton).toHaveAttribute('aria-expanded', 'true');
    await expect(recursiveLink).toBeInViewport();
    await expect(lookaheadLink).toBeInViewport();
    // Click recursive analysis
    await recursiveLink.click();
    await expect(page).toHaveURL(/recursive_analysis/);
    await expect(
      page.getByRole('heading', { name: 'Recursive analysis', level: 1 }),
    ).toBeInViewport();
    // Click lookahead analysis
    await lookaheadLink.click();
    await expect(page).toHaveURL(/lookahead_analysis/);
    await expect(
      page.getByRole('heading', { name: 'Lookahead analysis', level: 1 }),
    ).toBeInViewport();
  });

  test('Lookahead analysis test', async ({ page }) => {
    await page.route('**/api/v1/lookahead_analysis**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          path: './e2e/testData/analysis/lookahead_post_start.json',
        });
      } else if (route.request().method() === 'GET') {
        await route.fulfill({
          path: './e2e/testData/analysis/lookahead_get_end.json',
        });
      }
    });

    let lookaheadStatusCounter = 0;
    await page.route('**/api/v1/background/*', async (route) => {
      lookaheadStatusCounter++;
      if (lookaheadStatusCounter > 1) {
        await route.fulfill({
          path: './e2e/testData/analysis/lookahead_status_2.json',
        });
      } else {
        await route.fulfill({
          path: './e2e/testData/analysis/lookahead_status_1.json',
        });
      }
    });

    await page.goto('/lookahead_analysis');
    await expect(
      page.getByRole('heading', { name: 'Lookahead analysis', level: 1 }),
    ).toBeInViewport();

    await expect(page.getByRole('button', { name: 'Start lookahead analysis' })).not.toBeEnabled();
    await page.locator('#strategy-select').click();
    await page.getByText('AverageStrategy').click();
    await expect(page.getByRole('button', { name: 'Start lookahead analysis' })).toBeEnabled();
    await page.getByRole('button', { name: 'Start lookahead analysis' }).click();

    // Delays by a second due to background task timing
    const resultHeading = page.getByRole('heading', { name: 'Result', exact: true });
    await expect(resultHeading).toBeVisible();
    // The result panel renders below the settings form.
    await page.getByText('No lookahead bias detected').scrollIntoViewIfNeeded();
    await expect(resultHeading).toBeInViewport();
    await expect(page.getByText('No lookahead bias detected')).toBeInViewport();
    await expect(page.getByRole('cell', { name: 'AverageStrategy' })).toBeInViewport();
    await expect(page.getByText('No lookahead bias detected')).toBeInViewport();
  });

  test('Recursive analysis test', async ({ page }) => {
    await page.route('**/api/v1/recursive_analysis**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          path: './e2e/testData/analysis/recursive_post_start.json',
        });
      } else if (route.request().method() === 'GET') {
        await route.fulfill({
          path: './e2e/testData/analysis/recursive_get_end.json',
        });
      }
    });

    let recursiveStatusCounter = 0;
    await page.route('**/api/v1/background/*', async (route) => {
      recursiveStatusCounter++;
      if (recursiveStatusCounter > 1) {
        await route.fulfill({
          path: './e2e/testData/analysis/recursive_status_2.json',
        });
      } else {
        await route.fulfill({
          path: './e2e/testData/analysis/recursive_status_1.json',
        });
      }
    });

    await page.goto('/recursive_analysis');
    await expect(
      page.getByRole('heading', { name: 'Recursive analysis', level: 1 }),
    ).toBeInViewport();
    await expect(page.getByRole('button', { name: 'Start recursive analysis' })).not.toBeEnabled();
    await page.locator('#strategy-select').click();
    await page.getByText('AverageStrategy').click();
    await expect(page.getByRole('button', { name: 'Start recursive analysis' })).toBeEnabled();
    await page.getByRole('button', { name: 'Start recursive analysis' }).click();

    // Delays by a second due to background task timing
    const resultHeading = page.getByRole('heading', { name: 'Result', exact: true });
    await expect(resultHeading).toBeVisible();
    // The result panel renders below the settings form.
    await page
      .getByText('4 indicator(s) affected by startup candle count')
      .scrollIntoViewIfNeeded();
    await expect(resultHeading).toBeInViewport();
    await expect(
      page.getByText('4 indicator(s) affected by startup candle count'),
    ).toBeInViewport();
    await expect(page.getByRole('cell', { name: 'rsi' })).toBeVisible();
    await expect(page.getByText('4 indicator(s) affected by')).toBeInViewport();
    await expect(page.getByRole('cell', { name: 'rsi' })).toBeVisible();
    await expect(page.getByRole('cell', { name: '0.167%' })).toBeVisible();
  });
});
