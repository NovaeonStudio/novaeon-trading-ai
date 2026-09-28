import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { defaultMocks } from './helpers';

async function fillLoginForm(page: Page) {
  await page.getByRole('textbox', { name: 'Bot name' }).fill('TestBot');
  await page.getByRole('textbox', { name: 'Username' }).fill('novaeon');
  await page.getByRole('textbox', { name: 'Password' }).fill('SuperDuperBot');
}

test.describe('Login', () => {
  test('Is not logged in', async ({ page }) => {
    await page.goto('/');
    const connectButton = page.getByRole('banner').getByRole('button', { name: 'Connect a bot' });
    await expect(connectButton).toBeInViewport();

    await expect(page.getByText('No bot is connected yet.')).toBeVisible();
    await connectButton.click();
    const dialog = page.getByRole('dialog', { name: 'Connect your bot' });
    await expect(dialog).toBeVisible();
    // Test prefilled URL
    await expect(dialog.getByRole('textbox', { name: 'Bot address' })).toHaveValue(
      'http://localhost:3000',
    );
    await expect(dialog.getByRole('textbox', { name: 'Bot name' })).toBeVisible();
    await expect(dialog.getByRole('textbox', { name: 'Username' })).toBeVisible();
    await expect(dialog.getByRole('textbox', { name: 'Password' })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Connect' })).toBeVisible();
  });

  test('Explicit login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Connect your bot' })).toBeVisible();
    // The header does not offer the connect dialog on the login page itself.
    await expect(
      page.getByRole('banner').getByRole('button', { name: 'Connect a bot' }),
    ).not.toBeVisible();
    // Test prefilled URL
    await expect(page.getByRole('textbox', { name: 'Bot address' })).toHaveValue(
      'http://localhost:3000',
    );
    await expect(page.getByRole('textbox', { name: 'Bot name' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Connect' })).toBeVisible();
  });

  test('Redirect when not logged in', async ({ page }) => {
    await page.goto('/positions');
    await expect(page.getByRole('heading', { name: 'Connect your bot' })).toBeInViewport();
    await expect(page).toHaveURL(/.*\/login\?redirect=\/positions/);
  });

  test('Redirect from a legacy page when not logged in', async ({ page }) => {
    // Legacy URLs (e.g. /trade) forward to their successor page before the login check.
    await page.goto('/trade');
    await expect(page.getByRole('heading', { name: 'Connect your bot' })).toBeInViewport();
    await expect(page).toHaveURL(/.*\/login\?redirect=\/positions/);
  });

  test('Test Login', async ({ page }) => {
    await defaultMocks(page);
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Connect your bot' })).toBeVisible();

    await fillLoginForm(page);

    await page.route('**/api/v1/token/login', (route) => {
      return route.fulfill({
        status: 200,
        json: { access_token: 'access_token_tesst', refresh_token: 'refresh_test' },
        headers: { 'access-control-allow-origin': '*' },
      });
    });
    const loginButton = page.getByRole('button', { name: 'Connect' });
    await expect(loginButton).toBeVisible();
    await expect(loginButton).toHaveAttribute('type', 'submit');
    await Promise.all([loginButton.click(), page.waitForResponse('**/api/v1/token/login')]);

    // Logged in: the app menu replaces the connect button, the bot is listed on the bots page.
    await expect(page.getByRole('button', { name: 'App menu' })).toBeVisible();
    await expect(
      page.getByRole('banner').getByRole('button', { name: 'Connect a bot' }),
    ).not.toBeVisible();
    await page
      .getByRole('navigation', { name: 'Main' })
      .getByRole('link', { name: 'Bots' })
      .click();
    await expect(page.getByText('TestBot', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add a bot' })).toBeVisible();

    // Test logout
    await page.getByRole('button', { name: 'App menu' }).click();
    await page.getByRole('menuitem', { name: 'Log out' }).click();
    // Assert we're logged out again
    await expect(
      page.getByRole('banner').getByRole('button', { name: 'Connect a bot' }),
    ).toBeVisible();
  });

  test('Test Login failed - wrong api url', async ({ page }) => {
    await defaultMocks(page);
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Connect your bot' })).toBeVisible();
    await fillLoginForm(page);

    await page.route('**/api/v1/token/login', (route) => {
      return route.fulfill({
        status: 404,
        json: { access_token: 'access_token_tesst', refresh_token: 'refresh_test' },
        headers: { 'access-control-allow-origin': '*' },
      });
    });
    const loginButton = page.getByRole('button', { name: 'Connect' });
    await expect(loginButton).toBeVisible();
    await Promise.all([loginButton.click(), page.waitForResponse('**/api/v1/token/login')]);
    await expect(page.getByText('Could not connect')).toBeVisible();
    await expect(page.getByText('We could not reach a bot at')).toBeVisible();
    await expect(page.getByText('Enter the address of your bot.')).toBeVisible();
  });

  test('Test Login failed - wrong password', async ({ page }) => {
    await defaultMocks(page);
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Connect your bot' })).toBeVisible();
    await fillLoginForm(page);

    await page.route('**/api/v1/token/login', (route) => {
      return route.fulfill({
        status: 401,
        json: { access_token: 'access_token_tesst', refresh_token: 'refresh_test' },
        headers: { 'access-control-allow-origin': '*' },
      });
    });

    const loginButton = page.getByRole('button', { name: 'Connect' });
    await expect(loginButton).toBeVisible();
    await expect(page.getByText('Check the username.')).not.toBeVisible();
    await expect(page.getByText('Check the password.')).not.toBeVisible();
    await expect(
      page.getByText('The bot answered, but it did not accept this username and password.'),
    ).not.toBeVisible();

    await Promise.all([loginButton.click(), page.waitForResponse('**/api/v1/token/login')]);
    await expect(page.getByText('Check the username.')).toBeVisible();
    await expect(page.getByText('Check the password.')).toBeVisible();
    await expect(
      page.getByText('The bot answered, but it did not accept this username and password.'),
    ).toBeVisible();
  });
});
