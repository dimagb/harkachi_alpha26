import { setupServer } from 'msw/node';
import { afterAll, beforeEach, beforeAll, expect, it } from 'vitest';
import type { components } from '../api/schema';
import { createHandlers } from './handlers';
import { applicationScenarios } from './fixtures';

type Schema = components['schemas'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
beforeEach(() => server.resetHandlers(...createHandlers()));

async function request(path: string, token?: string, body?: Schema['LoginRequest'] | Schema['ApplicationCreate'] | Schema['CalculatorRequest']) {
  return fetch(new Request(`http://localhost/api/v1${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  }));
}
async function signIn(login: string) {
  const response = await request('/auth/login', undefined, { login, password: 'demo2026' });
  expect(response.status).toBe(200);
  const body: Schema['LoginResponse'] = await response.json();
  return body.access_token;
}

it.each([['ip_good', 'Смирнова Анна Викторовна', 'ИП Смирнова Анна Викторовна'], ['ooo_load', 'Петров Илья Игоревич', 'ООО «Северный склад»']])('MSW возвращает профиль персонажа %s', async (login, name, company) => {
  const token = await signIn(login);
  const response = await request('/me', token);
  const body: Schema['MeResponse'] = await response.json();
  expect(body.user.full_name).toBe(name);
  expect(body.companies[0]?.company.name).toBe(company);
});

it.each(['VALIDATION', 'INFO_REQUESTED', 'MANUAL_REVIEW', 'OFFER_ISSUED', 'DECLINED', 'SIGNING', 'DISBURSED', 'WITHDRAWN'] as const)('MSW отдаёт клиентскую фикстуру %s без внутренних данных', async (state) => {
  const token = await signIn('ip_good');
  const fixture = applicationScenarios.find((item) => item.state === state)!;
  const response = await request(`/applications/${fixture.id}`, token);
  expect(response.status).toBe(200);
  const body: Schema['ApplicationClient'] = await response.json();
  expect(body.state).toBe(state);
  expect(body.timeline).toHaveLength(6);
  expect(body.stage.title).toBe(body.timeline[body.stage.index - 1]!.title);
  expect(JSON.stringify(body)).not.toMatch(/risk_flag|internal_reasons|rules_fired|inputs_snapshot|SF_ADDITIONAL/);
});

async function withdraw(id: string, token?: string) {
  return fetch(`http://localhost/api/v1/applications/${id}/withdraw`, { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {} });
}
it('MSW отзывает заявку и сохраняет ответ, повтор возвращает 409', async () => {
  const token = await signIn('ip_good');
  const response = await withdraw('30000000-0000-4000-8000-000000000001', token);
  expect(response.status).toBe(200);
  const body: Schema['ApplicationClient'] = await response.json();
  expect(body).toMatchObject({ state: 'WITHDRAWN', version: 2, allowed_actions: ['NEW_APPLICATION'], stage: { what_happens: 'Заявка отозвана', what_to_do: 'Можно подать новую заявку' } });
  expect(body.timeline[3]!.status).toBe('cancelled');
  expect(await (await request(`/applications/${body.id}`, token)).json()).toEqual(body);
  expect((await withdraw(body.id, token)).status).toBe(409);
});
it('MSW проверяет доступ и состояние при отзыве', async () => {
  const ip = await signIn('ip_good');
  const other = await signIn('ooo_load');
  const accountant = await signIn('ooo_load_accountant');
  expect((await withdraw('missing', ip)).status).toBe(404);
  expect((await withdraw('30000000-0000-4000-8000-000000000001')).status).toBe(401);
  expect((await withdraw('30000000-0000-4000-8000-000000000001', other)).status).toBe(404);
  expect((await withdraw('30000000-0000-4000-8000-000000000002', accountant)).status).toBe(403);
  expect((await withdraw(applicationScenarios.find((item) => item.state === 'DISBURSED')!.id, ip)).status).toBe(409);
});

it.each([['EXPRESS', 300000, 6, 24, 53558], ['OVERDRAFT', 100000, 12, 26, null]] as const)('MSW считает платёж %s по контракту', async (product_code, amount, term_months, rate, payment) => {
  const token = await signIn('ip_good');
  const response = await request('/calculator', token, { product_code, amount, term_months });
  expect(response.status).toBe(200);
  const body: Schema['CalculatorResponse'] = await response.json();
  expect(body).toEqual({ rate_estimate: rate, monthly_payment: payment });
});

it.each(['ip_good', 'ooo_load'])('MSW отдаёт публичный профиль компании %s', async (login) => {
  const token = await signIn(login);
  const me: Schema['MeResponse'] = await (await request('/me', token)).json();
  const company = me.companies[0]!.company;
  const response = await request(`/companies/${company.id}/profile`, token);
  expect(response.status).toBe(200);
  const body: Schema['CompanyProfile'] = await response.json();
  expect(body).toMatchObject({ ...company, status: 'ACTIVE', director_full_name: me.user.full_name });
  expect(body.ogrn).toMatch(/^\d{13,15}$/);
  expect(body.avg_monthly_turnover).toBeGreaterThan(0);
  expect(body.source_note).toMatch(/Данные из ЕГР(ЮЛ|ИП) на/);
  expect(JSON.stringify(body)).not.toMatch(/risk_flag|internal_reasons|factors|rules_fired|inputs_snapshot|SF_ADDITIONAL/);
});

it('MSW защищает профиль компании и калькулятор', async () => {
  const token = await signIn('ooo_load');
  expect((await request('/companies/20000000-0000-4000-8000-000000000001/profile', token)).status).toBe(404);
  expect((await request('/companies/20000000-0000-4000-8000-000000000001/profile')).status).toBe(401);
  expect((await request('/calculator', undefined, { product_code: 'EXPRESS', amount: 300000, term_months: 6 })).status).toBe(401);
});

it.each([
  { amount: 299999 }, { amount: 5000001 }, { amount: 300000.5 },
  { term_months: 5 }, { term_months: 37 },
  { declared_revenue_year: 0 }, { declared_revenue_year: -1 },
  { purpose: 'OTHER' as const }, { purpose: 'OTHER' as const, purpose_text: 'коротко' },
  { purpose: 'OTHER' as const, purpose_text: 'а'.repeat(501) },
])('MSW показывает поля ошибки создания %j', async (invalid) => {
  const token = await signIn('ip_good');
  const response = await request('/applications', token, {
    company_id: '20000000-0000-4000-8000-000000000001', product_code: 'EXPRESS', amount: 300000,
    term_months: 6, purpose: 'WORKING_CAPITAL', declared_revenue_year: 12000000, ...invalid,
  });
  expect(response.status).toBe(422);
  const body: Schema['ApiError'] = await response.json();
  const field = 'purpose' in invalid ? 'purpose_text' : Object.keys(invalid)[0]!;
  expect(body.error.code).toBe('VALIDATION_ERROR');
  expect(body.error.details.fields).toHaveProperty(field);
});

it('MSW отклоняет невалидный расчёт с ошибкой под полем', async () => {
  const token = await signIn('ip_good');
  const response = await request('/calculator', token, { product_code: 'EXPRESS', amount: 1, term_months: 5 });
  expect(response.status).toBe(422);
  const body: Schema['ApiError'] = await response.json();
  expect(body.error.details.fields).toHaveProperty('amount');
  expect(body.error.details.fields).toHaveProperty('term_months');
});

it('MSW поддерживает учётку сотрудника банка', async () => {
  const token = await signIn('underwriter');
  const response = await request('/me', token);
  const body: Schema['MeResponse'] = await response.json();
  expect(body.user.role).toBe('UNDERWRITER');
  expect(body.companies).toEqual([]);
});

it('MSW отклоняет неизвестный токен и неверный пароль', async () => {
  expect((await request('/me', 'invalid')).status).toBe(401);
  expect((await request('/auth/login', undefined, { login: 'ip_good', password: 'wrong' })).status).toBe(401);
});

it('MSW отдаёт каталог трёх продуктов', async () => {
  const response = await request('/products');
  expect(response.status).toBe(200);
  const body: Schema['Product'][] = await response.json();
  expect(body).toEqual([
    { code: 'EXPRESS', name: 'Экспресс-кредит', description: 'На любые цели бизнеса', purposes: ['WORKING_CAPITAL', 'CASH_GAP', 'EQUIPMENT', 'OTHER'], requires_guarantor_ooo: true, min_amount: 300000, max_amount: 5000000, min_term_months: 6, max_term_months: 36, rate_from: 22.0, key_rate: 14.0, key_rate_date: '2026-10-23' },
    { code: 'WORKING_CAPITAL', name: 'Оборотный кредит', description: 'На пополнение оборотных средств', purposes: ['WORKING_CAPITAL', 'CASH_GAP'], requires_guarantor_ooo: true, min_amount: 500000, max_amount: 15000000, min_term_months: 3, max_term_months: 24, rate_from: 21.0, key_rate: 14.0, key_rate_date: '2026-10-23' },
    { code: 'OVERDRAFT', name: 'Овердрафт', description: 'На покрытие кассовых разрывов', purposes: ['CASH_GAP', 'WORKING_CAPITAL'], requires_guarantor_ooo: true, min_amount: 100000, max_amount: 5000000, min_term_months: 12, max_term_months: 12, rate_from: 24.0, key_rate: 14.0, key_rate_date: '2026-10-23' },
  ]);
});

it.each([['ip_good', 1500000, 'APPROVED'], ['ooo_load', 2850000, 'COUNTER']])('MSW отдаёт клиентские данные заявки %s', async (login, amount, kind) => {
  const token = await signIn(login);
  const me: Schema['MeResponse'] = await (await request('/me', token)).json();
  const list: Schema['ApplicationListItem'][] = await (await request(`/applications?company_id=${me.companies[0]?.company.id}`, token)).json();
  expect(list).toHaveLength(1);
  const response = await request(`/applications/${list[0]?.id}`, token);
  const body: Schema['ApplicationClient'] = await response.json();
  expect(body.offer?.amount).toBe(amount);
  expect(body.offer?.kind).toBe(kind);
  expect(JSON.stringify(body)).not.toMatch(/risk_flag|internal_reasons|factors|rules_fired|inputs_snapshot|SF_ADDITIONAL/);
});

it('MSW сохраняет созданный черновик и закрывает его от другого клиента', async () => {
  const token = await signIn('ip_good');
  const me: Schema['MeResponse'] = await (await request('/me', token)).json();
  const companyId = me.companies[0]!.company.id;
  const response = await request('/applications', token, { company_id: companyId, product_code: 'EXPRESS', amount: 1000000, term_months: 12, purpose: 'WORKING_CAPITAL', declared_revenue_year: 14000000 });
  expect(response.status).toBe(201);
  const created: Schema['ApplicationClient'] = await response.json();
  expect(created.state).toBe('DRAFT');
  expect(created.amount).toBe(1000000);
  const detail: Schema['ApplicationClient'] = await (await request(`/applications/${created.id}`, token)).json();
  expect(detail).toEqual(created);
  const list: Schema['ApplicationListItem'][] = await (await request(`/applications?company_id=${companyId}`, token)).json();
  expect(list[0]?.id).toBe(created.id);
  const otherToken = await signIn('ooo_load');
  expect((await request(`/applications/${created.id}`, otherToken)).status).toBe(403);
  expect((await request(`/applications?company_id=${companyId}`, otherToken)).status).toBe(403);
});
