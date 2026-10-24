import { setupServer } from 'msw/node';
import { afterAll, beforeAll, beforeEach, expect, it } from 'vitest';
import type { components } from '../../../api/schema';
import { applicationScenarios } from '../../../mocks/fixtures';
import { createHandlers } from '../../../mocks/handlers';

type Application = components['schemas']['ApplicationClient'];
const server = setupServer();
const offerId = '30000000-0000-4000-8000-000000000001';
const badId = '30000000-0000-4000-8000-000000000201';
const infoId = applicationScenarios.find((a) => a.state === 'INFO_REQUESTED')!.id;
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => server.resetHandlers(...createHandlers()));
afterAll(() => server.close());
function request(id: string, path = '', body?: unknown, login = 'ip_good') {
  return fetch(`http://localhost/api/v1/applications/${id}${path}`, { method: path ? 'POST' : 'GET', headers: { Authorization: `Bearer demo:${login}`, 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
}
it('MSW отвергает устаревшую версию без изменения оферты', async () => {
  const response = await request(offerId, '/offer/accept', { offer_version: 0 });
  expect(response.status).toBe(409);
  expect(await response.json()).toMatchObject({ error: { code: 'CONFLICT_VERSION' } });
  expect(await (await request(offerId)).json()).toMatchObject({ state: 'OFFER_ISSUED', offer: { status: 'ACTIVE' } });
});
it('MSW не принимает оферту за бухгалтера', async () => {
  const response = await request('30000000-0000-4000-8000-000000000002', '/offer/accept', { offer_version: 1 }, 'ooo_load_accountant');
  expect(response.status).toBe(403);
});
it('MSW не отдаёт чужую заявку и не меняет её действием', async () => {
  expect((await request(offerId, '', undefined, 'ooo_load')).status).toBe(403);
  expect((await request(offerId, '/offer/accept', { offer_version: 1 }, 'ooo_load')).status).toBe(404);
});
it('принятие сохраняет SIGNING; отзыв после принятия не возвращает устаревшее состояние', async () => {
  const accepted = await (await request(offerId, '/offer/accept', { offer_version: 1 })).json() as Application;
  expect(accepted).toMatchObject({ state: 'SIGNING', offer: { status: 'ACCEPTED' }, allowed_actions: ['WITHDRAW'] });
  expect(accepted.timeline.map((step) => step.status)).toEqual(['done', 'done', 'done', 'done', 'current', 'pending']);
  expect(await (await request(offerId)).json()).toEqual(accepted);
  expect((await request(offerId, '/withdraw')).status).toBe(200);
  expect(await (await request(offerId)).json()).toMatchObject({ state: 'WITHDRAWN' });
});
it('MSW сохраняет причину отклонения оферты и отменяет четвёртый этап', async () => {
  expect((await request(offerId, '/offer/reject')).status).toBe(200);
  const updated = await (await request(offerId)).json() as Application;
  expect(updated).toMatchObject({ state: 'WITHDRAWN', offer: { status: 'REJECTED' }, client_reason: { code: 'CLIENT_REJECTED_OFFER' }, allowed_actions: ['NEW_APPLICATION'] });
  expect(updated.timeline.map((step) => step.status)).toEqual(['done', 'done', 'done', 'cancelled', 'pending', 'pending']);
});
it.each(['123456789', 'x'.repeat(2001)])('MSW проверяет границы обращения (%s)', async (text) => {
  const response = await request(badId, '/objection', { text }, 'ip_bad');
  expect(response.status).toBe(422);
  expect(await response.json()).toMatchObject({ error: { details: { fields: { text: 'Введите от 10 до 2000 символов' } } } });
});
it.each([10, 2000])('MSW принимает %s символов и сохраняет пересмотр', async (length) => {
  expect((await request(badId, '/objection', { text: 'я'.repeat(length) }, 'ip_bad')).status).toBe(200);
  const updated = await (await request(badId, '', undefined, 'ip_bad')).json() as Application;
  expect(updated).toMatchObject({ state: 'MANUAL_REVIEW', objection: { status: 'PENDING' }, client_reason: null, allowed_actions: ['WITHDRAW'] });
  expect(updated.timeline.map((step) => step.status)).toEqual(['done', 'done', 'current', 'pending', 'pending', 'pending']);
});
it.each([
  { answers: [], field: 'answers' },
  { answers: [{ item_code: 'REVENUE_CONFIRM', value: 0, comment: 'Верно' }], field: 'answers.0.value' },
  { answers: [{ item_code: 'REVENUE_CONFIRM', value: 1.5, comment: 'Верно' }], field: 'answers.0.value' },
  { answers: [{ item_code: 'REVENUE_CONFIRM', value: 100, comment: 'Да' }], field: 'answers.0.comment' },
  { answers: [{ item_code: 'REVENUE_CONFIRM', value: 100, comment: 'я'.repeat(1001) }], field: 'answers.0.comment' },
  { answers: [{ item_code: 'PURPOSE_DETAILS', comment: 'Верно' }], field: 'answers' },
  { answers: [{ item_code: 'REVENUE_CONFIRM', value: 100, comment: 'Верно' }, { item_code: 'REVENUE_CONFIRM', value: 100, comment: 'Верно' }], field: 'answers' },
])('MSW отклоняет неверный набор ответов %#', async ({ answers, field }) => {
  const response = await request(infoId, '/info-response', { answers });
  expect(response.status).toBe(422);
  expect(await response.json()).toMatchObject({ error: { code: 'VALIDATION_ERROR', details: { fields: { [field]: expect.any(String) } } } });
  expect(await (await request(infoId)).json()).toMatchObject({ state: 'INFO_REQUESTED' });
});
it('MSW принимает ответ, закрывает запрос и отклоняет повторный ответ', async () => {
  const body = { answers: [{ item_code: 'REVENUE_CONFIRM', value: 14000000, comment: 'Часть выручки в другом банке' }] };
  expect((await request(infoId, '/info-response', body)).status).toBe(200);
  const updated = await (await request(infoId)).json() as Application;
  expect(updated).toMatchObject({ state: 'VALIDATION', info_request: null, allowed_actions: ['WITHDRAW'] });
  expect(updated.timeline.map((step) => step.status)).toEqual(['done', 'current', 'pending', 'pending', 'pending', 'pending']);
  expect((await request(infoId, '/info-response', body)).status).toBe(409);
});
