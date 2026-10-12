import type { Page } from '@playwright/test';
import { test, expect, API, noHorizontalOverflow } from './fixtures';

const routes = [
  ['/', 'Evidence, then automation.'],
  ['/archetypes', 'Enterprise Archetype Workbench'],
  ['/distillation', 'Model Distillation Studio'],
  ['/social-deck', 'Pixel-Perfect Social Carousel & Infographics'],
  ['/showcase', 'AutoPilot FDE 2.0'],
  ['/channels', 'Observation sources'],
  ['/processes', 'Process map'],
  ['/objects', 'Object Lens'],
  ['/scores', 'Automation opportunity'],
  ['/deploy', 'Create a draft pilot'],
  ['/performance', 'Pilot performance'],
] as const;

const routeReads: Record<string, string[]> = {
  '/': ['/dashboard/'], '/channels': ['/channels/'],
  '/processes': ['/processes/', '/scores/'], '/scores': ['/processes/', '/scores/'],
  '/objects': ['/processes/object-log?limit=500'],
  '/deploy': ['/processes/', '/scores/', '/agents/'], '/performance': ['/agents/'],
};

async function navigateReady(page: Page, route: string) {
  const reads = (routeReads[route] || []).map(path => page.waitForResponse(r =>
    r.url() === `${API}${path}` && r.request().method() === 'GET'));
  const response = await page.goto(route);
  expect(response?.ok()).toBe(true);
  for (const read of reads) expect((await read).ok()).toBe(true);
  // Wait for rendered data, not just the heading/server HTML, before layout QA.
  if (route === '/') {
    const data = await (await reads[0]).json();
    await expect(page.getByRole('heading', { name: 'Processes discovered', exact: true }).locator('..').locator('p')).toHaveText(String(data.processes_discovered));
  } else if (route === '/channels') {
    const data = await (await reads[0]).json();
    for (const channel of data) await expect(page.getByRole('heading', { name: channel.name, exact: true })).toBeVisible();
    await expect(page.getByText('Loading channel information…')).toHaveCount(0);
  } else if (route === '/processes') {
    await expect(page.getByText('Selected workflow', { exact: true })).toBeVisible();
    await expect(page.getByText('Loading workflows…')).toHaveCount(0);
  } else if (route === '/scores') {
    await expect(page.getByRole('heading', { name: 'Score explanation', exact: true })).toBeVisible();
  } else if (route === '/objects') {
    const data = await (await reads[0]).json();
    await expect(page.locator('tbody tr')).toHaveCount(data.objects.length);
    await expect(page.getByText('Loading object log…')).toHaveCount(0);
  } else if (route === '/deploy') {
    await expect(page.getByRole('button', { name: 'Create draft pilot', exact: true })).toBeEnabled();
    await expect(page.getByText('Loading deployment records…')).toHaveCount(0);
  } else if (route === '/performance') {
    const data = await (await reads[0]).json();
    if (data.length) for (const agent of data) await expect(page.getByText(agent.name, { exact: true }).first()).toBeVisible();
    else await expect(page.getByText('No pilot agents yet. Create a limited draft pilot from the Deploy page.')).toBeVisible();
    await expect(page.getByText('Loading agent records…')).toHaveCount(0);
  }
}

for (const [route, title] of routes) {
  test(`live route ${route} renders its heading and navigation`, async ({ page }) => {
    await navigateReady(page, route);
    await expect(page.getByRole('heading', { level: 1, name: title, exact: true })).toBeVisible();
    await expect(page.getByRole('navigation').getByRole('link')).toHaveCount(routes.length);
  });
  test(`mobile layout ${route} remains navigable without page overflow`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await navigateReady(page, route);
    await expect(page.getByRole('heading', { level: 1, name: title, exact: true })).toBeVisible();
    await noHorizontalOverflow(page);
  });
}

test('sidebar remains named when collapsed and supports keyboard/back/forward', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /collapse.*(sidebar|navigation)/i }).click();
  const processes = page.getByRole('navigation').getByRole('link', { name: 'Processes', exact: true });
  await processes.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL('/processes');
  await page.getByRole('navigation').getByRole('link', { name: 'Scores', exact: true }).click();
  await expect(page).toHaveURL('/scores');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Process map', exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading', { name: 'Automation opportunity', exact: true })).toBeVisible();
});

test('dashboard and channels display seeded API values', async ({ page, request }) => {
  const dashboard = await (await request.get(`${API}/dashboard/`)).json();
  expect(dashboard.processes_discovered).toBeGreaterThan(0);
  await page.goto('/');
  const value = page.getByRole('heading', { name: 'Processes discovered', exact: true }).locator('..').locator('p');
  await expect(value).toHaveText(String(dashboard.processes_discovered));
  const channels = await (await request.get(`${API}/channels/`)).json();
  expect(channels.length).toBeGreaterThan(0);
  await page.goto('/channels');
  for (const channel of channels) await expect(page.getByRole('heading', { name: channel.name, exact: true })).toBeVisible();
});

test('process discovery refreshes real fixture evidence and workflow graph', async ({ page, request }) => {
  await page.goto('/processes');
  await expect(page.getByText('Selected workflow', { exact: true })).toBeVisible();
  const response = page.waitForResponse(r => r.url() === `${API}/processes/discover` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run discovery', exact: true }).click();
  expect((await response).ok()).toBe(true);
  await expect(page.getByText(/workflows rebuilt from .* source-linked activities/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Evidence-linked steps' })).toBeVisible();
  const processes = await (await request.get(`${API}/processes/`)).json();
  expect(processes.length).toBeGreaterThan(1);
  const target = processes.at(-1);
  await page.locator(`.react-flow__node[data-id=${JSON.stringify(target.id)}]`).click();
  await expect(page.locator('main aside').getByRole('heading', { name: target.name, exact: true })).toBeVisible();
  expect(target.activities.length).toBeGreaterThan(0);
  await expect(page.locator('main aside')).toContainText(target.activities[0].evidence);
});

test('scores display API workflows and select a workflow by keyboard', async ({ page, request }) => {
  const processes = await (await request.get(`${API}/processes/`)).json();
  await page.goto('/scores');
  await expect(page.getByRole('heading', { name: 'Score explanation' })).toBeVisible();
  const name = processes.at(-1).name;
  const selector = page.getByRole('button', { name: `Show score for ${name}`, exact: true });
  await selector.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('main aside')).toContainText(name);
});

test('object types filter actual objects and selected traces show evidence', async ({ page, request }) => {
  const log = await (await request.get(`${API}/processes/object-log?limit=500`)).json();
  expect(log.objects.length).toBeGreaterThan(0);
  await page.goto('/objects');
  const object = log.objects[0];
  await page.getByRole('button', { name: object.id, exact: true }).click();
  const trace = log.events.filter((event: { relationships: Array<{ objectId: string }> }) => event.relationships.some(rel => rel.objectId === object.id)).sort((a: { time: string }, b: { time: string }) => a.time.localeCompare(b.time));
  expect(trace.length).toBeGreaterThan(0);
  const tracePanel = page.locator('main aside');
  await expect(tracePanel).toContainText(object.id);
  await expect(tracePanel.locator('ol li')).toHaveCount(trace.length);
  for (const [index, event] of trace.entries()) {
    await expect(tracePanel.locator('ol li').nth(index)).toContainText(event.type);
    await expect(tracePanel.locator('ol li').nth(index)).toContainText(event.time);
    const evidence = event.attributes.find((attribute: { name: string }) => attribute.name === 'evidence');
    if (evidence) await expect(tracePanel.locator('ol li').nth(index)).toContainText(String(evidence.value));
  }
  const typeButton = page.getByRole('button').filter({ hasText: object.type }).first();
  await typeButton.click();
  const rows = page.locator('tbody tr');
  for (const row of await rows.all()) await expect(row).toContainText(object.type);
});

for (const route of ['/channels', '/scores', '/objects', '/deploy']) {
  test(`injected API failure ${route} is visible rather than reported as success`, async ({ page }) => {
    await page.route(`${API}/**`, r => r.fulfill({ status: 503, json: { detail: 'Synthetic test outage' } }));
    await page.goto(route);
    await expect(page.getByText(/Synthetic test outage/).first()).toBeVisible();
  });
}

test('empty channel and score fixtures stop loading and explain the empty result', async ({ page }) => {
  await page.route(`${API}/channels/`, r => r.fulfill({ json: [] }));
  await page.goto('/channels');
  await expect(page.getByText(/No .*sources|No .*channels/i)).toBeVisible();
  await expect(page.getByText('Loading channel information…')).toHaveCount(0);
  await page.route(`${API}/processes/`, r => r.fulfill({ json: [] }));
  await page.route(`${API}/scores/`, r => r.fulfill({ json: [] }));
  await page.goto('/scores');
  await expect(page.getByText(/No scored workflows|No .*scores/i).first()).toBeVisible();
  await expect(page.getByText('Loading score explanation…')).toHaveCount(0);
});

test('showcase controls remain explicitly illustrative', async ({ page }) => {
  await page.goto('/showcase');
  await expect(page.getByText(/numbers and code samples below are illustrative fixtures/)).toBeVisible();
  await page.getByRole('button', { name: 'LangGraph Code Synthesis', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Synthesized Python LangGraph State Machine' })).toBeVisible();
  await page.getByRole('button', { name: /Verified Verification Matrix/ }).click();
  await expect(page.getByText(/Verified Functional/).first()).toBeVisible();
  await page.getByRole('button', { name: 'Monte Carlo Simulator', exact: true }).click();
  await expect(page.getByRole('slider')).toBeVisible();
  await page.getByRole('slider').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('slider')).toHaveValue('81');
});

test('social themes change locally and clipboard failure never claims success', async ({ page }) => {
  // Inject a browser capability failure, not an application/API result.
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', {
    configurable: true, value: { writeText: () => Promise.reject(new Error('Clipboard unavailable in test')) },
  }));
  await page.goto('/social-deck');
  await page.getByRole('button', { name: 'Copy Post', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  await expect(page.getByText('Copied!', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '2. AutoPilot FDE: 4-Panel Editorial' }).click();
  await expect(page.getByText(/AutoPilot/).first()).toBeVisible();
  await page.getByRole('button', { name: '3. 5-Slide Master Pitch Deck' }).click();
  await expect(page.getByRole('button', { name: /Copy.*(Tweet|Post)/i }).first()).toBeVisible();
});

test('mobile navigation and alternate showcase/social panels stay reachable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await navigateReady(page, '/');
  const performance = page.getByRole('navigation').getByRole('link', { name: 'Performance', exact: true });
  await performance.scrollIntoViewIfNeeded();
  await performance.click();
  await expect(page.getByRole('heading', { name: 'Pilot performance', exact: true })).toBeVisible();
  await noHorizontalOverflow(page);
  await page.goto('/showcase');
  await page.getByRole('button', { name: 'LangGraph Code Synthesis', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Synthesized Python LangGraph State Machine' })).toBeVisible();
  await noHorizontalOverflow(page);
  await page.getByRole('button', { name: /Verified Verification Matrix/ }).click();
  await expect(page.getByText(/Verified Functional/).first()).toBeVisible();
  await noHorizontalOverflow(page);
  await page.goto('/social-deck');
  await page.getByRole('button', { name: '2. AutoPilot FDE: 4-Panel Editorial' }).click();
  await noHorizontalOverflow(page);
  await page.getByRole('button', { name: '3. 5-Slide Master Pitch Deck' }).click();
  await expect(page.getByRole('button', { name: /Copy.*(Tweet|Post)/i }).first()).toBeVisible();
  await noHorizontalOverflow(page);
});
