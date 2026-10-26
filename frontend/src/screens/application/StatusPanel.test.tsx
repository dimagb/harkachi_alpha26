import { MantineProvider } from '@mantine/core';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import type { components } from '../../api/schema';
import { createHandlers } from '../../mocks/handlers';
import StatusPanel from './StatusPanel';

type Application = components['schemas']['ApplicationClient'];
const server = setupServer(...createHandlers());
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
afterEach(cleanup);

it.each([
  ['DECLINED', '2026-11-23', 'default'],
  ['DECLINED', null, null],
  ['EXPIRED', '2026-11-23', null],
] as const)('%s, повтор с %s: вид новой заявки — %s', async (state, retryAfter, variant) => {
  const declined = await (await fetch('http://localhost/api/v1/applications/30000000-0000-4000-8000-000000000201', { headers: { Authorization: 'Bearer demo:ip_bad' } })).json() as Application;
  const application: Application = { ...declined, state, client_reason: { ...declined.client_reason!, retry_after: retryAfter } };
  render(<MantineProvider env="test"><MemoryRouter><StatusPanel application={application} status="failed" /></MemoryRouter></MantineProvider>);
  const link = within(screen.getByRole('region', { name: 'Что происходит с заявкой' })).getByRole('link', { name: 'Подать новую заявку' });
  expect(link.getAttribute('data-variant')).toBe(variant);
  expect(link.getAttribute('href')).toBe('/app/applications/new');
});

it.each([
  [0, 'true'],
  [1, 'false'],
] as const)('этап %i: прямой угол под указателем — %s', async (step, first) => {
  const declined = await (await fetch('http://localhost/api/v1/applications/30000000-0000-4000-8000-000000000201', { headers: { Authorization: 'Bearer demo:ip_bad' } })).json() as Application;
  const application: Application = { ...declined, stage: { ...declined.stage, code: declined.timeline[step]!.stage_code } };
  render(<MantineProvider env="test"><MemoryRouter><StatusPanel application={application} status="current" /></MemoryRouter></MantineProvider>);
  expect(screen.getByRole('region', { name: 'Что происходит с заявкой' }).getAttribute('data-first')).toBe(first);
});
