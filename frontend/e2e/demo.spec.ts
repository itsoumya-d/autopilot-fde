import { performance } from 'node:perf_hooks';
import { writeFile } from 'node:fs/promises';
import { test, expect, API, openWorkbench } from './fixtures';

// Recording is opt-in. The default CI job retains/uploads NOTHING. A recording
// run needs a separately reviewed retention/download path; it is not publishing.
const recording = process.env.AUTOPILOT_RECORD_DEMO === '1';
test.use({
  viewport: { width: 1600, height: 1000 },
  video: recording ? { mode: 'on', size: { width: 1600, height: 1000 } } : 'off',
});

test('demonstration: genuine invoice recovery and final resolved refund ticket', async ({ page }, testInfo) => {
  test.setTimeout(recording ? 150_000 : 60_000);
  const start = performance.now();
  const shots: Array<{ label: string; milliseconds: number }> = [];
  const shot = async (label: string) => {
    shots.push({ label, milliseconds: Math.round(performance.now() - start) });
    // Short genuine holds keep the raw upload bounded. Longer caption-reading
    // pauses are added locally after retrieval, disclosed as editing pauses.
    if (recording) await page.waitForTimeout(2_000);
  };
  await openWorkbench(page, '3. Document Intelligence');
  await expect(page.getByText(/Connected API selected\. Results appear only after/)).toBeVisible();
  await shot('Connected API; synthetic fixture boundary');
  await page.getByRole('checkbox', { name: 'Inject a sample $10 arithmetic discrepancy' }).check();
  const invalidResponse = page.waitForResponse(`${API}/archetypes/project3/validate-invoice`);
  await page.getByRole('button', { name: 'Run Deterministic Audit', exact: true }).click();
  expect((await (await invalidResponse).json()).math_delta).toBe(-10);
  await page.getByText('Sample validation failed', { exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByText('Sample validation failed', { exact: true })).toBeInViewport();
  await shot('Actual invoice failure; ten-dollar discrepancy');
  await page.getByRole('checkbox', { name: 'Inject a sample $10 arithmetic discrepancy' }).uncheck();
  await page.getByRole('button', { name: 'Run Deterministic Audit', exact: true }).click();
  await page.getByText('Sample arithmetic checks passed', { exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByText('Sample arithmetic checks passed', { exact: true })).toBeInViewport();
  await shot('Corrected invoice passes');
  await page.getByRole('tab', { name: '2. Intake-to-Resolution', exact: true }).click();
  await expect(page.getByLabel('Sample ticket content')).toHaveValue('Urgent: need refund of $450 on corporate billing');
  await page.getByLabel('Sample ticket content').scrollIntoViewIfNeeded();
  await expect(page.getByLabel('Sample ticket content')).toBeInViewport();
  await shot('Synthetic refund input');
  const ingestedResponse = page.waitForResponse(`${API}/archetypes/project2/ticket`);
  await page.getByRole('button', { name: 'Ingest Ticket', exact: true }).click();
  const pending = await (await ingestedResponse).json();
  expect(pending.status).toBe('pending_approval');
  await expect(page.getByText(pending.id, { exact: true })).toBeVisible();
  await page.getByText('pending_approval', { exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByText('pending_approval', { exact: true })).toBeInViewport();
  await shot('Same ticket awaits review');
  const approvedResponse = page.waitForResponse(`${API}/archetypes/project2/approve`);
  await page.getByRole('button', { name: 'Approve Sample Ticket', exact: true }).click();
  const resolved = await (await approvedResponse).json();
  expect(resolved.id).toBe(pending.id);
  expect(resolved.status).toBe('resolved');
  expect(resolved.approval_token).toBeNull();
  await expect(page.getByText(pending.id, { exact: true })).toBeVisible();
  await page.getByText('API confirmed the ticket is resolved.', { exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByText('API confirmed the ticket is resolved.', { exact: true })).toBeInViewport();
  await expect(page.getByRole('button', { name: 'Approve Sample Ticket', exact: true })).toHaveCount(0);
  await expect(page.getByText(pending.id, { exact: true })).toBeInViewport();
  await shot('Confirmed resolved ticket; no refund issued');
  const evidencePath = testInfo.outputPath('demonstration-evidence.json');
  await writeFile(evidencePath, JSON.stringify({
    recording, source: 'Real browser UI and real API in this isolated test runner',
    synthetic: true, ticketId: resolved.id, finalStatus: resolved.status,
    externalActions: false, shots, sourceCommit: process.env.GITHUB_SHA ?? null,
  }, null, 2));
  await testInfo.attach('demonstration-evidence.json', {
    path: evidencePath, contentType: 'application/json',
  });
});
