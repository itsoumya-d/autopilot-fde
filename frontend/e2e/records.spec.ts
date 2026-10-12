import { test, expect, API } from './fixtures';

test('live pilot record lifecycle changes records without starting a worker', async ({ page, request }) => {
  await page.goto('/deploy');
  await expect(page.getByRole('button', { name: 'Create draft pilot', exact: true })).toBeEnabled();
  await expect(page.getByText('This page does not start a hosted worker or route live traffic.', { exact: false })).toBeVisible();
  const slider = page.getByRole('slider', { name: 'Configured traffic percentage' });
  await slider.focus();
  await page.keyboard.press('End');
  await expect(slider).toHaveValue('50');
  const createdResponse = page.waitForResponse(r => r.url() === `${API}/agents/deploy` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create draft pilot', exact: true }).click();
  const created = await (await createdResponse).json();
  expect(created.status).toBe('pending_approval');
  expect(created.config.traffic_percentage).toBe(50);
  const group = page.getByTestId(`agent-record-${created.id}`);
  await expect(group).toContainText('Pending approval');
  await group.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(group).toContainText('Running');
  await group.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect(group).toContainText('Paused');
  await group.getByRole('button', { name: 'Resume', exact: true }).click();
  await expect(group).toContainText('Running');
  await page.getByRole('navigation').getByRole('link', { name: 'Performance', exact: true }).click();
  await expect(page.getByText(created.name, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Illustrative pilot trend' })).toBeVisible();
  await page.getByRole('navigation').getByRole('link', { name: 'Deploy', exact: true }).click();
  await page.getByTestId(`agent-record-${created.id}`).getByRole('button', { name: `Remove ${created.name}`, exact: true }).click();
  await expect(page.getByText('Agent record removed.', { exact: true })).toBeVisible();
  const saved = await (await request.get(`${API}/agents/`)).json();
  expect(saved.some((agent: { id: string }) => agent.id === created.id)).toBe(false);
});

test('deployment failed load requires explicit refresh before mutation', async ({ page }) => {
  await page.route(`${API}/agents/`, r => r.fulfill({ status: 503, json: { detail: 'Synthetic records outage' } }));
  await page.goto('/deploy');
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Synthetic records outage');
  await expect(page.getByRole('button', { name: 'Create draft pilot', exact: true })).toBeDisabled();
  await page.unroute(`${API}/agents/`);
  await page.getByRole('button', { name: 'Retry refresh', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Create draft pilot', exact: true })).toBeEnabled();
});

test('live redaction preview clears on edit and synthetic recipe files are reported truthfully', async ({ page, request }) => {
  await page.goto('/distillation');
  const generate = page.getByRole('button', { name: 'Compile Dataset & Generate Training Recipes', exact: true });
  await expect(generate).toBeDisabled();
  await page.getByLabel('Sample operational text').fill('Synthetic email demo@example.com and phone 555-019-2834.');
  await page.getByRole('button', { name: 'Test PII Sanitizer', exact: true }).click();
  await expect(page.getByText(/Backend preview \(/)).toBeVisible();
  await page.getByLabel('Sample operational text').fill('A different synthetic sample.');
  await expect(page.getByText(/Backend preview \(/)).toHaveCount(0);
  // These local test-only scenario declarations neither accept external terms
  // nor call a teacher, train a model, or grant a provider license.
  await page.getByRole('checkbox', { name: 'I intend to use these artifacts for internal enterprise workflow automation.' }).check();
  await expect(generate).toBeDisabled();
  await page.getByRole('checkbox', { name: 'I will not use these artifacts to develop or sell a competing general-purpose foundation model service.' }).check();
  const generated = page.waitForResponse(r => r.url() === `${API}/distillation/jobs` && r.request().method() === 'POST');
  await generate.click();
  const response = await generated;
  expect(response.ok()).toBe(true);
  const job = await response.json();
  expect(job.status).toBe('completed');
  expect(job.sample_count).toBeGreaterThan(0);
  await expect(page.getByRole('region', { name: 'Generation result' })).toContainText('Dataset and recipes generated');
  await expect(page.getByText(/No model was trained or deployed/)).toBeVisible();
  const saved = await (await request.get(`${API}/distillation/jobs/${job.id}`)).json();
  expect(saved.id).toBe(job.id);
  await page.getByLabel('Teacher model reference (metadata only)').selectOption('deepseek-r1');
  await expect(page.getByRole('region', { name: 'Generation result' })).toHaveCount(0);
});
