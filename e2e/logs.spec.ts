import { test, expect } from '@playwright/test';

import { setLoginInfo, defaultMocks, getWaitForResponse } from './helpers';

test.describe('Logs', () => {
  test('Displays and reloads logs', async ({ page }) => {
    ///
    await defaultMocks(page);
    await setLoginInfo(page);

    await page.route('**/api/v1/logs', (route) => {
      return route.fulfill({ path: './e2e/testData/logs.json' });
    });

    const logs = getWaitForResponse(page, '@Logs');
    const ping = getWaitForResponse(page, '@ShowConf');
    // The legacy /logs page forwards to the Journal.
    await Promise.all([page.goto('/logs'), logs, ping]);
    await expect(page).toHaveURL(/\/journal$/);
    await expect(page.getByRole('heading', { name: 'Journal', level: 1 })).toBeVisible();

    await expect(page.getByText(/Checking exchange\.\.\./)).toBeVisible();
    const logsPromise = getWaitForResponse(page, '@Logs');
    await page.getByRole('button', { name: 'Reload the log' }).click();
    await logsPromise;
  });
});
