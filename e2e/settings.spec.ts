import { test, expect } from '@playwright/test';
import { setLoginInfo, defaultMocks } from './helpers';

test.describe('Settings', () => {
  test('Settings stores', async ({ page }) => {
    await setLoginInfo(page);
    await defaultMocks(page);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Bots', level: 1 })).toBeInViewport({
      timeout: 5000,
    });
    const appMenu = page.getByRole('button', { name: 'App menu' });
    await expect(appMenu).toBeVisible();
    await appMenu.click();
    await page.getByRole('menuitem', { name: 'Settings' }).click();

    await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible();
    await expect(page).toHaveURL('http://localhost:3000/settings');

    // Switch option in the settings.
    const openTradesSelect = page.getByRole('combobox', { name: 'Open trades in the header' });
    await expect(openTradesSelect).toHaveText('Badge on the tab icon');
    await openTradesSelect.click();
    await page.getByRole('option', { name: 'Count in the page title' }).click();
    await expect(openTradesSelect).toHaveText('Count in the page title');

    const settings = await page.evaluate(() =>
      JSON.parse(window.localStorage.getItem('ftUISettings') || '{}'),
    );
    await expect(settings['openTradesInTitle']).toBe('asTitle');
  });
});
