import { test as base, expect, type Page } from '@playwright/test';

export const API = 'http://127.0.0.1:8000/api';
export const test = base.extend<{ browserSafety: void }>({
  browserSafety: [async ({ context }, use, testInfo) => {
    const externalRequests: string[] = [];
    const pageErrors: string[] = [];
    const observe = (tab: Page) => tab.on('pageerror', error => pageErrors.push(error.message));
    context.pages().forEach(observe);
    context.on('page', observe);
    // App navigation must remain inside this test runner's own two services.
    // Intentionally blocked requests fail the test; they are never relayed.
    await context.route(/^https?:\/\//, async route => {
      const url = new URL(route.request().url());
      if (url.hostname === '127.0.0.1' && ['3000', '8000'].includes(url.port)) {
        await route.continue();
      } else {
        externalRequests.push(`${url.origin}${url.pathname}`);
        await route.abort('blockedbyclient');
      }
    });
    await use();
    await testInfo.attach('browser-safety.json', {
      body: JSON.stringify({ externalRequests, pageErrors }), contentType: 'application/json',
    });
    expect(externalRequests, 'No intercepted browser HTTP(S) request may target an external service').toEqual([]);
    expect(pageErrors, 'No uncaught browser JavaScript errors').toEqual([]);
  }, { auto: true }],
});
export { expect };

export async function openWorkbench(page: Page, tab = '2. Intake-to-Resolution') {
  await page.goto('/archetypes');
  await expect(page.getByRole('radio', { name: 'Connected API', exact: true })).toBeChecked();
  await page.getByRole('tab', { name: tab, exact: true }).click();
}

export async function noHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => {
    const main = document.querySelector('main')!;
    const bounds = main.getBoundingClientRect();
    return {
      page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      main: main.scrollWidth - main.clientWidth,
      // Bounded layout diagnostics for a genuine failure, without media uploads.
      overflowing: Array.from(main.querySelectorAll('*')).filter(element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && (rect.right > bounds.right + 1 || rect.left < bounds.left - 1);
      }).slice(0, 12).map(element => ({
        tag: element.tagName, className: element.getAttribute('class'),
        width: Math.round(element.getBoundingClientRect().width),
      })),
    };
  });
  expect(dimensions.page, 'Document must fit the viewport').toBeLessThanOrEqual(1);
  expect(dimensions.main, `Main content must not require horizontal scrolling: ${JSON.stringify(dimensions)}`).toBeLessThanOrEqual(1);
}
