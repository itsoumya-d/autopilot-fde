import { test, expect, API, openWorkbench } from './fixtures';

const prefix = `${API}/archetypes`;

test('live refund: one pending ticket becomes resolved; replay is refused', async ({ page, request }) => {
  await openWorkbench(page);
  const ingested = page.waitForResponse(`${prefix}/project2/ticket`);
  await page.getByRole('button', { name: 'Ingest Ticket', exact: true }).click();
  const ticket = await (await ingested).json();
  expect(ticket.status).toBe('pending_approval');
  await expect(page.getByText(ticket.id, { exact: true })).toBeVisible();
  await expect(page.getByText('pending_approval', { exact: true })).toBeVisible();
  const bad = await request.post(`${prefix}/project2/approve`, { data: {
    ticket_id: ticket.id, approval_token: 'synthetic-wrong-token', operator: 'Browser test reviewer',
  } });
  expect(bad.status()).toBe(400);
  const approved = page.waitForResponse(`${prefix}/project2/approve`);
  await page.getByRole('button', { name: 'Approve Sample Ticket', exact: true }).click();
  const resolved = await (await approved).json();
  expect(resolved.id).toBe(ticket.id);
  expect(resolved.approval_token).toBeNull();
  await expect(page.getByText('API confirmed the ticket is resolved.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve Sample Ticket', exact: true })).toHaveCount(0);
  const replay = await request.post(`${prefix}/project2/approve`, { data: {
    ticket_id: ticket.id, approval_token: ticket.approval_token, operator: 'Browser test reviewer',
  } });
  expect(replay.status()).toBe(409);
  const saved = await (await request.get(`${prefix}/project2/tickets`)).json();
  expect(saved.find((item: { id: string }) => item.id === ticket.id)).toEqual(resolved);
});

test('live invoice fails on discrepancy and passes after explicit correction', async ({ page }) => {
  await openWorkbench(page, '3. Document Intelligence');
  await page.getByRole('checkbox', { name: 'Inject a sample $10 arithmetic discrepancy' }).check();
  await page.getByRole('button', { name: 'Run Deterministic Audit', exact: true }).click();
  await expect(page.getByText('Sample validation failed', { exact: true })).toBeVisible();
  await expect(page.getByText(/Math delta: \$-10\.00/)).toBeVisible();
  await page.getByRole('checkbox', { name: 'Inject a sample $10 arithmetic discrepancy' }).uncheck();
  await expect(page.getByText('Sample validation failed', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Run Deterministic Audit', exact: true }).click();
  await expect(page.getByText('Sample arithmetic checks passed', { exact: true })).toBeVisible();
  await expect(page.getByText(/Math delta: \$0\.00/)).toBeVisible();
});

test('live role-filtered knowledge, onboarding quarantine and single-use rollback', async ({ page }) => {
  await openWorkbench(page, '1. Knowledge RAG');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('Role filter passed', { exact: true })).toBeVisible();
  await expect(page.getByText(/Sample citation:/).first()).toBeVisible();
  await page.getByRole('radio', { name: 'guest', exact: true }).check();
  await page.getByRole('button', { name: 'Executive compensation', exact: true }).click();
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('Blocked by sample role filter', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: '4. Data Onboarding', exact: true }).click();
  await page.getByRole('button', { name: 'Process Sample CSV Batch', exact: true }).click();
  await expect(page.getByText('Accepted rows', { exact: true }).locator('..')).toContainText('2');
  await expect(page.getByText('Quarantined rows', { exact: true }).locator('..')).toContainText('3');
  await expect(page.getByText(/Row 2:/)).toBeVisible();
  await page.getByRole('tab', { name: '5. Ops Command Center', exact: true }).click();
  await page.getByRole('button', { name: 'Run Sample Incident', exact: true }).click();
  await expect(page.getByText('Record state: remediated', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Roll Back Sample Incident', exact: true }).click();
  await expect(page.getByText('API confirmed the synthetic incident was rolled back.', { exact: true })).toBeVisible();
  await expect(page.getByText('Record state: rolled_back', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Roll Back Sample Incident', exact: true })).toHaveCount(0);
});

test('injected outage shows failure, keeps connected mode, and explicit retry succeeds', async ({ page }) => {
  await openWorkbench(page);
  await page.route(`${prefix}/project2/ticket`, r => r.abort('failed'));
  await page.getByRole('button', { name: 'Ingest Ticket', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Request failed:');
  await expect(page.getByRole('radio', { name: 'Connected API', exact: true })).toBeChecked();
  await expect(page.getByText('pending_approval', { exact: true })).toHaveCount(0);
  await page.unroute(`${prefix}/project2/ticket`);
  await page.getByRole('button', { name: 'Ingest Ticket', exact: true }).click();
  await expect(page.getByText('pending_approval', { exact: true })).toBeVisible();
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
});

test('delayed real response locks repeated submit and cannot repaint a dismissed panel', async ({ page }) => {
  await openWorkbench(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let seen!: () => void;
  const received = new Promise<void>(resolve => { seen = resolve; });
  let done!: () => void;
  const completed = new Promise<void>(resolve => { done = resolve; });
  let confirmedAbort = false;
  let routeFailure: unknown;
  let requests = 0;
  await page.route(`${prefix}/project2/ticket`, async route => {
    requests += 1;
    try {
      const response = await route.fetch({ maxRedirects: 0 });
      expect(response.ok()).toBe(true);
      expect((await response.json()).status).toBe('pending_approval');
      seen();
      await gate;
      try { await route.fulfill({ response }); }
      catch (error) { if (!confirmedAbort) throw error; }
    } catch (error) { routeFailure = error; }
    finally { done(); }
  });
  try {
    await page.getByRole('button', { name: 'Ingest Ticket', exact: true }).click();
    await received;
    const pending = page.getByRole('button', { name: 'Ingesting…', exact: true });
    await expect(pending).toBeDisabled();
    await expect(page.getByLabel('Sample ticket content')).toBeDisabled();
    const box = await pending.boundingBox();
    if (!box) throw new Error('Pending button is not visible');
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2, { clickCount: 2 });
    const aborted = page.waitForEvent('requestfailed', { predicate: request => request.url() === `${prefix}/project2/ticket` });
    await page.getByRole('tab', { name: '3. Document Intelligence', exact: true }).click();
    expect((await aborted).failure()?.errorText).toContain('ERR_ABORTED');
    confirmedAbort = true;
    release();
    await completed;
    expect(routeFailure).toBeUndefined();
    await page.getByRole('tab', { name: '2. Intake-to-Resolution', exact: true }).click();
    await expect(page.getByText('Ingest a sample ticket to inspect its state.', { exact: true })).toBeVisible();
    await expect(page.getByText('pending_approval', { exact: true })).toHaveCount(0);
    expect(requests).toBe(1);
  } finally {
    release();
  }
});

test('malformed response cannot become success and mode switching clears evidence', async ({ page }) => {
  await openWorkbench(page);
  await page.route(`${prefix}/project2/ticket`, r => r.fulfill({ json: { status: 'resolved' } }));
  await page.getByRole('button', { name: 'Ingest Ticket', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('unexpected response');
  await expect(page.getByText(/confirmed the ticket is resolved/)).toHaveCount(0);
  await page.getByRole('radio', { name: 'Synthetic demo (local)', exact: true }).check();
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  await expect(page.getByText('Ingest a sample ticket to inspect its state.', { exact: true })).toBeVisible();
  await page.getByRole('radio', { name: 'Connected API', exact: true }).check();
  await expect(page.getByText('Ingest a sample ticket to inspect its state.', { exact: true })).toBeVisible();
});

test('workbench tabs support arrow, Home and End keyboard navigation', async ({ page }) => {
  await openWorkbench(page, '1. Knowledge RAG');
  await page.getByRole('tab', { name: '1. Knowledge RAG', exact: true }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: '2. Intake-to-Resolution', exact: true })).toBeFocused();
  await expect(page.getByRole('heading', { name: 'Intake-to-resolution workflow', exact: true })).toBeVisible();
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', { name: '5. Ops Command Center', exact: true })).toBeFocused();
  await page.keyboard.press('Home');
  await expect(page.getByRole('tab', { name: '1. Knowledge RAG', exact: true })).toBeFocused();
});
