import { test, expect, API } from './fixtures';

test('live pilot record lifecycle changes records without starting a worker', async ({ page, request }) => {
  await page.goto('/deploy');
  await expect(page.getByRole('button', { name: 'Create draft pilot', exact: true })).toBeEnabled();
  // The highest-scored demo workflow has unsupported mined edge names.
  // Exercise the lifecycle with a complete supported chain instead of
  // silently relying on whichever score happens to be first.
  const processesResponse = await request.get(`${API}/processes/`);
  expect(processesResponse.ok()).toBe(true);
  const processes = await processesResponse.json();
  const supported = processes.find((process: { name: string }) => process.name === 'Customer Success Renewal Triage');
  expect(supported).toBeDefined();
  await page.getByLabel('Evidence-backed workflow').selectOption(supported.id);
  await expect(page.getByText('This page does not start a hosted worker or route live traffic.', { exact: false })).toBeVisible();
  const slider = page.getByRole('slider', { name: 'Configured traffic percentage' });
  await slider.focus();
  await page.keyboard.press('End');
  await expect(slider).toHaveValue('50');
  const createdResponse = page.waitForResponse(r => r.url() === `${API}/agents/deploy` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create draft pilot', exact: true }).click();
  const response = await createdResponse;
  expect(response.status(), await response.text()).toBe(201);
  const created = await response.json();
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
  await page.getByRole('navigation').getByRole('link', { name: 'Pilots', exact: true }).click();
  await page.getByTestId(`agent-record-${created.id}`).getByRole('button', { name: `Remove ${created.name}`, exact: true }).click();
  await expect(page.getByText('Agent record removed.', { exact: true })).toBeVisible();
  const saved = await (await request.get(`${API}/agents/`)).json();
  expect(saved.some((agent: { id: string }) => agent.id === created.id)).toBe(false);
});

test('unsupported mined topology shows rejection and creates no pilot record', async ({ page, request }) => {
  const before = await (await request.get(`${API}/agents/`)).json();
  const processes = await (await request.get(`${API}/processes/`)).json();
  const unsupported = processes.find((process: { name: string }) => process.name === 'Enterprise Deal Desk & Inbound Lead Routing');
  expect(unsupported).toBeDefined();
  await page.goto('/deploy');
  await expect(page.getByRole('button', { name: 'Create draft pilot', exact: true })).toBeEnabled();
  await page.getByLabel('Evidence-backed workflow').selectOption(unsupported.id);
  const rejectedResponse = page.waitForResponse(r => r.url() === `${API}/agents/deploy` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create draft pilot', exact: true }).click();
  const rejected = await rejectedResponse;
  expect(rejected.status()).toBe(422);
  expect((await rejected.json()).detail).toBe('Mined edges must reference exact workflow step names.');
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Mined edges must reference exact workflow step names.');
  await expect(page.getByText('Pilot record created. Pending human approval; no worker was started.', { exact: true })).toHaveCount(0);
  const after = await (await request.get(`${API}/agents/`)).json();
  expect(after).toEqual(before);
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
