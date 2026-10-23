import { setupServer } from 'msw/node';
import { afterAll, beforeEach, beforeAll, expect, it } from 'vitest';
import type { components } from '../api/schema';
import { createHandlers } from './handlers';

type Schema = components['schemas'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
beforeEach(() => server.resetHandlers(...createHandlers()));

async function request(path: string, token?: string, body?: Schema['LoginRequest'] | Schema['ApplicationCreate']) {
  return fetch(new Request(`http://localhost/api/v1${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  }));
}
async function signIn(login: string) {
  const response = await request('/auth/login', undefined, { login, password: 'demo' });
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
  const body: Schema['Product'][] = await response.json();
  expect(body.map(({ code }) => code)).toEqual(['EXPRESS', 'WORKING_CAPITAL', 'OVERDRAFT']);
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
