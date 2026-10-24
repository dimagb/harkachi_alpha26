import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, beforeAll, beforeEach, expect, it } from 'vitest';
import type { components } from '../../api/schema';
import { createBankHandlers } from './handlers';
import { createJournalHandlers } from './journal';

type Schema = components['schemas'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
beforeEach(() => server.resetHandlers(...createJournalHandlers(), ...createBankHandlers(), http.all('*/api/v1/*', () => new HttpResponse(null, { status: 501 }))));
const root = 'http://localhost/api/v1';
async function request(path: string, body?: unknown, token = 'demo:underwriter') {
  return fetch(root + path, { method: body === undefined ? 'GET' : 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
}
async function list(query = ''): Promise<Schema['Page_BankListItem_']> { return (await request('/bank/applications' + query)).json(); }

it('пагинирует 28 заявок, фильтрует и оставляет карточки F-07 их обработчику', async () => {
  const first = await list('?page=1&size=20');
  expect(first).toMatchObject({ total: 28, page: 1, size: 20 });
  expect(first.items).toHaveLength(20);
  const second = await list('?page=2&size=20');
  expect(second.items).toHaveLength(8);
  expect(second.items.some(item => first.items.some(other => other.id === item.id))).toBe(false);
  const filtered = await list('?state=MANUAL_REVIEW');
  expect(filtered.items.length).toBeGreaterThan(0);
  expect(filtered.items.every(item => item.state === 'MANUAL_REVIEW')).toBe(true);
  const border: Schema['ApplicationBank'] = await (await request('/underwriting/applications/ooo_border')).json();
  expect(border.decisions[0]).toMatchObject({ score: 54 });
  for (const item of [...first.items, ...second.items]) {
    const response = await request(`/underwriting/applications/${item.id}`);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ id: item.id, state: item.state, events: expect.any(Array), decisions: expect.any(Array) });
  }
});

it.each(['?page=0', '?page=1.5', '?size=101', '?size=0', '?state=WRONG'])('отклоняет неверный фильтр %s', async query => {
  expect((await request('/bank/applications' + query)).status).toBe(422);
});

it.each([0, 401, 1.5, '31'])('отклоняет days=%s с details.fields.days', async days => {
  const response = await request('/demo/time-shift', { application_id: 'journal-1', days });
  expect(response.status).toBe(422);
  expect(await response.json()).toMatchObject({ error: { code: 'VALIDATION_ERROR', details: { fields: { days: expect.any(String) } } } });
});

it.each([['OFFER_ISSUED', 29, false], ['OFFER_ISSUED', 30, true], ['SIGNING', 30, true], ['INFO_REQUESTED', 4, false], ['INFO_REQUESTED', 5, true]] as const)('перематывает %s на %i дней: истечение=%s', async (state, days, expired) => {
  const app = (await list(`?state=${state}`)).items[0]!;
  const response = await request('/demo/time-shift', { application_id: app.id, days });
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual({ application_id: app.id, expired_now: expired, state: expired ? 'EXPIRED' : state });
  const detail: Schema['ApplicationBank'] = await (await request(`/underwriting/applications/${app.id}`)).json();
  expect(detail.state).toBe(expired ? 'EXPIRED' : state);
  if (expired) expect(detail.events.at(-1)).toMatchObject({ from_state: state, to_state: 'EXPIRED', note: expect.any(String) });
  expect((await list()).items.find(item => item.id === app.id)?.state).toBe(expired ? 'EXPIRED' : state);
});

it('учитывает несколько сдвигов и меняет срок в карточке', async () => {
  const app = (await list('?state=INFO_REQUESTED')).items[0]!;
  const before: Schema['ApplicationBank'] = await (await request(`/underwriting/applications/${app.id}`)).json();
  await request('/demo/time-shift', { application_id: app.id, days: 3 });
  const after: Schema['ApplicationBank'] = await (await request(`/underwriting/applications/${app.id}`)).json();
  expect(new Date(before.info_request!.due_at).getTime() - new Date(after.info_request!.due_at).getTime()).toBe(3 * 86400000);
  expect(await (await request('/demo/time-shift', { application_id: app.id, days: 2 })).json()).toMatchObject({ expired_now: true });
});

it('проверяет роль, неизвестный id и лишние поля', async () => {
  expect((await request('/bank/applications', undefined, 'demo:ip_good')).status).toBe(403);
  expect((await request('/bank/applications', undefined, 'wrong')).status).toBe(401);
  expect((await request('/demo/time-shift', { application_id: 'missing', days: 31 })).status).toBe(404);
  expect((await request('/demo/time-shift', { application_id: 'journal-1', days: 31, extra: true })).status).toBe(422);
});

it('все заявки на рассмотрении специалиста принимают решение через F-07', async () => {
  const manual = await list('?state=MANUAL_REVIEW');
  for (const app of manual.items) {
    const response = await request(`/underwriting/${app.id}/decision`, { outcome: 'APPROVE', amount: app.amount, term_months: 24, comment: 'Данные проверены специалистом' });
    expect(response.status, app.id).toBe(200);
  }
});
