import { readFileSync } from 'node:fs';
import { setupServer } from 'msw/node';
import { afterAll, beforeAll, beforeEach, expect, it } from 'vitest';
import type { components } from '../../api/schema';
import { createBankHandlers } from './handlers';

type Schema = components['schemas'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
beforeEach(() => server.resetHandlers(...createBankHandlers()));
const root = 'http://localhost/api/v1/underwriting';
async function request(path: string, body?: unknown, token = 'demo:underwriter') {
  return fetch(`${root}${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
}
async function application(id = 'ooo_border'): Promise<Schema['ApplicationBank']> {
  return (await request(`/applications/${id}`)).json();
}

it('отдаёт эталон ooo_border и первоисточники без импорта contracts в src', async () => {
  const personas = JSON.parse(readFileSync('../contracts/personas.json', 'utf8'));
  const persona = personas.personas.find((p: { code: string }) => p.code === 'ooo_border');
  const app = await application();
  const decision = app.decisions[0]!;
  const expected = persona.demo.expected;
  expect(app.state).toBe(expected.state);
  expect(decision).toMatchObject({ outcome: 'MANUAL', route_reason: expected.route_reason, grade: expected.recommendation.grade, score: expected.recommendation.score });
  expect(Object.fromEntries(decision.factors.map(f => [f.code, f.points]))).toEqual(expected.recommendation.points);
  expect(decision.recommendation).toEqual({ outcome: expected.recommendation.outcome, amount: expected.recommendation.offer.amount, term_months: expected.recommendation.offer.term_months, rate: expected.recommendation.offer.rate });
  expect(app.turnover_12m.map(m => m.amount)).toEqual(persona.turnover);
  expect(app.external_checks.find(c => c.source === 'BKI')?.response).toMatchObject(persona.bki);
  expect(app.external_checks.find(c => c.source === 'FNS')?.response).toMatchObject(persona.fns);
});

it('охраняет банк от клиента и неизвестной сессии, возвращает 404', async () => {
  expect((await request('/queue', undefined, 'demo:ip_good')).status).toBe(403);
  expect((await request('/queue', undefined, 'wrong')).status).toBe(401);
  expect((await request('/applications/missing')).status).toBe(404);
});

it.each([
  ['APPROVE', { amount: 1000000, term_months: 24 }, 'OFFER_ISSUED'],
  ['COUNTER', { amount: 800000, term_months: 24 }, 'OFFER_ISSUED'],
  ['DECLINE', { client_reason_category: 'Финансовое положение' }, 'DECLINED'],
  ['REQUEST_INFO', { info_questions: ['Подтвердите поступления за месяц'] }, 'INFO_REQUESTED'],
  ['RETRY_ENRICHMENT', {}, 'ENRICHMENT'],
] as const)('сохраняет %s, протокол, расхождение и удаляет из очереди', async (outcome, fields, state) => {
  const id = outcome === 'RETRY_ENRICHMENT' ? 'source_unavailable' : 'ooo_border';
  const result = await request(`/${id}/decision`, { outcome, ...fields, comment: 'Проверены первичные сведения' });
  expect(result.status).toBe(200);
  const updated: Schema['ApplicationBank'] = await result.json();
  expect(updated.state).toBe(state);
  expect(updated.decisions[0]).toMatchObject({ kind: 'MANUAL', outcome, made_by: 'Орлова Мария Андреевна', comment: 'Проверены первичные сведения' });
  expect(updated.events.some(e => e.event_type === 'DECISION_MADE')).toBe(true);
  expect(updated.events.some(e => e.event_type === 'UNDERWRITER_OVERRIDE')).toBe(outcome !== 'APPROVE');
  expect(await application(id)).toEqual(updated);
  const queue: Schema['QueueItem'][] = await (await request('/queue')).json();
  expect(queue.some(item => item.id === id)).toBe(false);
  expect((await request(`/${id}/decision`, { outcome, ...fields, comment: 'Повторное решение' })).status).toBe(409);
});

it.each([
  [{ outcome: 'APPROVE', amount: 1000000, term_months: 24, comment: '' }, 'comment'],
  [{ outcome: 'APPROVE', amount: 1, term_months: 24, comment: 'Проверено' }, 'amount'],
  [{ outcome: 'APPROVE', amount: 999999, term_months: 24, comment: 'Проверено' }, 'amount'],
  [{ outcome: 'COUNTER', amount: 1000000.5, term_months: 24, comment: 'Проверено' }, 'amount'],
  [{ outcome: 'COUNTER', amount: 1000000, term_months: 100, comment: 'Проверено' }, 'term_months'],
  [{ outcome: 'COUNTER', amount: 1000000, term_months: 24, comment: 'Проверено' }, 'amount'],
  [{ outcome: 'DECLINE', comment: 'Проверено' }, 'client_reason_category'],
  [{ outcome: 'REQUEST_INFO', info_questions: [], comment: 'Проверено' }, 'info_questions'],
  [{ outcome: 'REQUEST_INFO', info_questions: ['мало'], comment: 'Проверено' }, 'info_questions'],
  [{ outcome: 'REQUEST_INFO', info_questions: Array(6).fill('Подтвердите выручку'), comment: 'Проверено' }, 'info_questions'],
  [{ outcome: 'DECLINE', client_reason_category: 'Данные о компании', comment: 'а'.repeat(2001) }, 'comment'],
  [{ outcome: 'DECLINE', client_reason_category: 'Данные о компании', comment: 'Проверено', extra: true }, 'extra'],
])('возвращает 422 для невалидного решения %j', async (body, field) => {
  const response = await request('/ooo_border/decision', body);
  expect(response.status).toBe(422);
  expect((await response.json()).error.details.fields).toHaveProperty(field);
  expect((await application()).state).toBe('MANUAL_REVIEW');
});

it('разрешает повторный сбор только при SOURCE_UNAVAILABLE, AML остаётся отказом', async () => {
  expect((await request('/ooo_border/decision', { outcome: 'RETRY_ENRICHMENT', comment: 'Повторить сбор' })).status).toBe(409);
  const failed = await application('source_unavailable');
  expect(failed.external_checks.find(c => c.source === 'BKI')).toMatchObject({ status: 'FAILED', attempts: 3 });
  const aml = await application('ooo_aml');
  expect(aml).toMatchObject({ state: 'DECLINED', risk_flags: { aml_flag: true } });
  expect(aml.decisions[0]?.rules_fired).toContainEqual(expect.objectContaining({ code: 'SF_ADDITIONAL', effect: 'STOP' }));
});
