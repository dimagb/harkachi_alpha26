import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import type { components } from '../../api/schema';
import { applications, accounts, draftApplication } from '../fixtures';
import { createSigningHandlers } from './signing';

type Schema = components['schemas'];
type Application = Schema['ApplicationClient'];
const server = setupServer();
let stored: Map<string, Application>;
const ipId = '30000000-0000-4000-8000-000000000301';
const oooId = '30000000-0000-4000-8000-000000000302';
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => {
  stored = new Map([0, 1].map((index) => {
    const base = applications[index]!; const id = index ? oooId : ipId;
    return [id, draftApplication(base, id, 1301 + index)];
  }));
  server.resetHandlers(...createSigningHandlers(stored));
});
afterEach(() => vi.useRealTimers());
afterAll(() => server.close());
function request(id: string, path = '', body?: unknown, login = 'ip_good') {
  return fetch(`http://localhost/api/v1/applications/${id}${path}`, { method: path ? 'POST' : 'GET', headers: { Authorization: `Bearer demo:${login}`, 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
}
async function otp(id: string, purpose = 'CONSENTS', login = 'ip_good', party_id?: string) {
  return (await (await request(id, '/otp', { purpose, ...(party_id ? { party_id } : {}) }, login)).json()) as Schema['OtpResponse'];
}
it('выдаёт шестизначный код на 5 минут и подаёт заявку единожды', async () => {
  const started = Date.now(); const code = await otp(ipId);
  expect(code.demo_code).toMatch(/^\d{6}$/);
  expect(Date.parse(code.expires_at) - started).toBeGreaterThanOrEqual(300000);
  expect(Date.parse(code.expires_at) - started).toBeLessThan(301000);
  const body = { otp_id: code.otp_id, code: code.demo_code, consents: { pdn: true, bki: true, auto_decision: true } };
  const response = await request(ipId, '/submit', body); expect(response.status).toBe(200);
  const application = await response.json() as Application;
  expect(application.state).toBe('SUBMITTED');
  expect(application.awaiting_signature).toBe(false);
  expect(application.parties).toEqual([{ id: expect.any(String), role: 'BORROWER_SIGNATORY', full_name: accounts.ip_good!.user.full_name, signed: false, is_me: true }]);
  expect(application.stage).toMatchObject({ index: 1, what_happens: 'Заявка отправлена, скоро начнём проверку', what_to_do: null });
  expect(application.timeline.map((step) => step.status)).toEqual(['current', 'pending', 'pending', 'pending', 'pending', 'pending']);
  expect((await request(ipId, '/submit', body)).status).toBe(409);
});
it('проверяет код, срок и обязательные согласия, не меняя состояние', async () => {
  const code = await otp(ipId);
  const body = { otp_id: code.otp_id, code: '000000', consents: { pdn: true, bki: true, auto_decision: false } };
  expect((await request(ipId, '/submit', body)).status).toBe(422);
  expect(stored.get(ipId)!.state).toBe('DRAFT');
  expect((await request(ipId, '/submit', { ...body, code: code.demo_code, consents: { ...body.consents, pdn: false } })).status).toBe(422);
  vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(Date.parse(code.expires_at));
  const response = await request(ipId, '/submit', { ...body, code: code.demo_code });
  expect(await response.json()).toMatchObject({ error: { code: 'OTP_INVALID', message: 'Код недействителен или истёк' } });
});
it('бухгалтер не получает код согласий, отправляет директору идемпотентно; директор подаёт', async () => {
  expect((await request(oooId, '/otp', { purpose: 'CONSENTS' }, 'ooo_load_accountant')).status).toBe(403);
  const first = await (await request(oooId, '/request-signature', undefined, 'ooo_load_accountant')).json();
  const second = await (await request(oooId, '/request-signature', undefined, 'ooo_load_accountant')).json();
  expect(first).toEqual(second); expect(first).toMatchObject({ awaiting_signature: true, allowed_actions: ['EDIT_DRAFT', 'WITHDRAW'] });
  const code = await otp(oooId, 'CONSENTS', 'ooo_load');
  const response = await request(oooId, '/submit', { otp_id: code.otp_id, code: code.demo_code, consents: { pdn: true, bki: true, auto_decision: false } }, 'ooo_load');
  const submitted = await response.json() as Application;
  expect(submitted.state).toBe('SUBMITTED'); expect(submitted.parties.map((p) => [p.role, p.is_me])).toEqual([['BORROWER_SIGNATORY', true], ['GUARANTOR', true]]);
});
it('две подписи ООО требуют отдельные коды и завершаются выдачей через 2 секунды', async () => {
  const base = stored.get(oooId)!;
  const parties: Application['parties'] = [
    { id: 'borrower', role: 'BORROWER_SIGNATORY', full_name: accounts.ooo_load!.user.full_name, signed: false, is_me: true },
    { id: 'guarantor', role: 'GUARANTOR', full_name: accounts.ooo_load!.user.full_name, signed: false, is_me: true },
  ];
  stored.set(oooId, { ...base, state: 'SIGNING', parties, offer: { ...applications[1]!.offer!, status: 'ACCEPTED' } });
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] });
  const borrower = await otp(oooId, 'OFFER', 'ooo_load', 'borrower');
  expect((await request(oooId, '/sign', { otp_id: borrower.otp_id, code: borrower.demo_code, party_id: 'guarantor' }, 'ooo_load')).status).toBe(422);
  const first = await (await request(oooId, '/sign', { otp_id: borrower.otp_id, code: borrower.demo_code, party_id: 'borrower' }, 'ooo_load')).json() as Application;
  expect(first.parties.map((p) => p.signed)).toEqual([true, false]); expect(first.state).toBe('SIGNING');
  const guarantor = await otp(oooId, 'GUARANTEE', 'ooo_load', 'guarantor');
  const response = await request(oooId, '/sign', { otp_id: guarantor.otp_id, code: guarantor.demo_code, party_id: 'guarantor' }, 'ooo_load');
  expect(await response.json()).toMatchObject({ state: 'SIGNED', allowed_actions: [] });
  await vi.advanceTimersByTimeAsync(1999); expect(stored.get(oooId)!.state).toBe('SIGNED');
  await vi.advanceTimersByTimeAsync(1); expect(stored.get(oooId)).toMatchObject({ state: 'DISBURSED', allowed_actions: ['NEW_APPLICATION'] });
  expect(stored.get(oooId)!.timeline.map((step) => step.status)).toEqual(['done', 'done', 'done', 'done', 'done', 'done']);
});
it('цель, состояние, владелец и party проверяются до выдачи кода', async () => {
  expect((await request(ipId, '/otp', { purpose: 'OFFER', party_id: 'no' })).status).toBe(409);
  expect((await request(ipId, '/otp', { purpose: 'UNKNOWN' })).status).toBe(422);
  expect((await request(ipId, '/otp', { purpose: 'CONSENTS', party_id: 'no' })).status).toBe(422);
  expect((await request(ipId, '/otp', { purpose: 'CONSENTS' }, 'ooo_load')).status).toBe(404);
  const base = stored.get(oooId)!;
  stored.set(oooId, { ...base, state: 'SIGNING', parties: [{ id: 'other', role: 'GUARANTOR', full_name: 'Другой участник', signed: false, is_me: false }] });
  expect((await request(oooId, '/otp', { purpose: 'GUARANTEE', party_id: 'other' }, 'ooo_load')).status).toBe(403);
  expect((await request(oooId, '/otp', { purpose: 'OFFER' }, 'ooo_load')).status).toBe(422);
});
