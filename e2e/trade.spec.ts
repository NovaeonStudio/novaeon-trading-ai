import { test, expect } from '@playwright/test';

import { setLoginInfo, defaultMocks, tradeMocks } from './helpers';

test.describe('Trade', () => {
  test.beforeEach(async ({ page }) => {
    await defaultMocks(page);
    await setLoginInfo(page);
    // The classic trade page's tools are Pro mode features in the new app.
    await page.evaluate(() => localStorage.setItem('nova-mode', 'pro'));

    await tradeMocks(page);
  });
  test('Trade page', async ({ page }) => {
    // The legacy /trade page forwards to Positions.
    await Promise.all([
      page.goto('/trade'),
      // Wait for network requests
      page.waitForResponse('**/status'),
      page.waitForResponse('**/profit'),
      page.waitForResponse('**/balance'),
    ]);
    await expect(page).toHaveURL(/\/positions$/);

    // Check visibility of elements
    await expect(page.getByRole('heading', { name: 'Positions', level: 1 })).toBeInViewport();
    await expect(page.getByRole('heading', { name: 'Open positions' })).toBeInViewport();
    await expect(page.getByText('No open positions.')).toBeVisible();

    // Test messageBox behavior
    const dialogModal = page.getByRole('dialog');
    const modalCancelButton = dialogModal.getByRole('button', { name: 'Cancel' });

    await expect(dialogModal).not.toBeVisible();
    await expect(dialogModal).not.toBeInViewport();

    await expect(modalCancelButton).not.toBeVisible();

    await page.getByRole('button', { name: 'Pause entries' }).click();

    // Modal open
    await expect(dialogModal).toBeVisible();
    await expect(dialogModal).toBeInViewport();
    await expect(dialogModal.getByText('Pause new entries?')).toBeVisible();
    await expect(modalCancelButton).toBeInViewport();

    // Close modal
    await modalCancelButton.click();

    // Modal closed
    await expect(modalCancelButton).not.toBeVisible();
    await expect(modalCancelButton).not.toBeInViewport();

    const sidebar = page.getByRole('navigation', { name: 'Main' });

    // Performance per pair (successor of the classic "Performance" tab)
    await Promise.all([
      page.waitForResponse('**/performance'),
      sidebar.getByRole('link', { name: 'Markets' }).click(),
    ]);
    await expect(page.getByRole('button', { name: /^XRP 74 trades/ })).toBeInViewport();

    // Closed trades
    await sidebar.getByRole('link', { name: 'Trades' }).click();
    await expect(page.getByRole('heading', { name: 'Trades', level: 1 })).toBeInViewport();
    await expect(page.getByRole('cell', { name: 'TRX 1x' })).toBeInViewport();
    await expect(page.getByRole('cell', { name: '0.06183 → 0.06185' })).toBeInViewport();

    // Reload Config (lives in the command palette now)
    await page.getByRole('button', { name: 'Open command palette' }).click();
    await page.getByRole('option', { name: 'Reload configuration' }).click();
    await expect(dialogModal).toBeVisible();
    await expect(dialogModal).toBeInViewport();
    await expect(dialogModal.getByText('Reload the configuration?')).toBeVisible();

    const modalOkButton = dialogModal.getByRole('button', { name: 'Confirm' });
    await expect(modalOkButton).toBeVisible();
    await Promise.all([page.waitForResponse('**/reload_config'), modalOkButton.click()]);

    const configReloadToast = page.getByText('Config reloaded successfully.', { exact: true });
    await expect(configReloadToast).toBeInViewport();
    await expect(configReloadToast).toBeVisible();
  });
});
