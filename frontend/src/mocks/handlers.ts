import { http, HttpResponse } from 'msw';
import type { components } from '../api/schema';
import { accounts, applications, applicationScenarios, companyProfiles, draftApplication, products } from './fixtures';
import { createDecisionHandlers } from './client/decision';
import { createSigningHandlers } from './client/signing';

type Schema = components['schemas'];
type ApiError = Schema['ApiError'];
type Application = Schema['ApplicationClient'];
type EmptyParams = Record<string, never>;

function error(status: number, code: ApiError['error']['code'], message: string, fields?: Record<string, string>) {
  return HttpResponse.json<ApiError>({ error: { code, message, details: fields ? { fields } : {} } }, { status });
}
function account(request: Request) {
  const header = request.headers.get('Authorization');
  return header?.startsWith('Bearer demo:') ? accounts[header.slice('Bearer demo:'.length)] : undefined;
}
function ownsCompany(me: Schema['MeResponse'], companyId: string) {
  return me.user.role === 'CLIENT' && me.companies.some(({ company }) => company.id === companyId);
}

export function createHandlers() {
  const stored = new Map(applications.map((application) => [application.id, application]));
  return [
    ...createDecisionHandlers(stored),
    ...createSigningHandlers(stored),
    http.post<EmptyParams, Schema['LoginRequest'], Schema['LoginResponse'] | ApiError>('*/api/v1/auth/login', async ({ request }) => {
      const body = await request.json();
      const me = accounts[body.login];
      if (!me || body.password !== 'demo2026') return error(401, 'UNAUTHORIZED', 'Неверный логин или пароль. Проверьте данные и повторите вход.');
      return HttpResponse.json({ access_token: `demo:${body.login}`, token_type: 'bearer', expires_in: 3600, user: me.user });
    }),
    http.get<EmptyParams, never, Schema['MeResponse'] | ApiError>('*/api/v1/me', ({ request }) => {
      const me = account(request);
      return me ? HttpResponse.json(me) : error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
    }),
    http.get<EmptyParams, never, Schema['Product'][]>('*/api/v1/products', () => HttpResponse.json(products)),
    http.post<EmptyParams, Schema['CalculatorRequest'], Schema['CalculatorResponse'] | ApiError>('*/api/v1/calculator', async ({ request }) => {
      const me = account(request);
      if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
      if (me.user.role !== 'CLIENT') return error(403, 'FORBIDDEN', 'Расчёт доступен клиенту.');
      const body = await request.json();
      const product = products.find(({ code }) => code === body.product_code);
      const fields: Record<string, string> = {};
      if (!product) fields.product_code = 'Выберите продукт.';
      if (!Number.isInteger(body.amount) || !product || body.amount < product.min_amount || body.amount > product.max_amount) fields.amount = 'Укажите целую сумму в пределах продукта.';
      if (!Number.isInteger(body.term_months) || !product || body.term_months < product.min_term_months || body.term_months > product.max_term_months) fields.term_months = 'Выберите срок в пределах продукта.';
      if (!product || Object.keys(fields).length) return error(422, 'VALIDATION_ERROR', 'Проверьте параметры расчёта.', fields);
      const rate = product.rate_from + 2;
      const monthlyRate = rate / 1200;
      const payment = Math.round(body.amount * monthlyRate / (1 - (1 + monthlyRate) ** -body.term_months));
      return HttpResponse.json({ rate_estimate: rate, monthly_payment: product.code === 'OVERDRAFT' ? null : payment });
    }),
    http.get<{ id: string }, never, Schema['CompanyProfile'] | ApiError>('*/api/v1/companies/:id/profile', ({ request, params }) => {
      const me = account(request);
      if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
      if (me.user.role !== 'CLIENT') return error(403, 'FORBIDDEN', 'Профиль компании доступен клиенту.');
      const profile = companyProfiles[params.id];
      if (!ownsCompany(me, params.id) || !profile) return error(404, 'NOT_FOUND', 'Компания не найдена.');
      return HttpResponse.json(profile);
    }),
    http.get<EmptyParams, never, Schema['ApplicationListItem'][] | ApiError>('*/api/v1/applications', ({ request }) => {
      const me = account(request);
      if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
      const companyId = new URL(request.url).searchParams.get('company_id');
      if (!companyId) return error(422, 'VALIDATION_ERROR', 'Выберите компанию.', { company_id: 'Выберите компанию.' });
      if (!ownsCompany(me, companyId)) return error(403, 'FORBIDDEN', 'Нет доступа к заявкам этой компании.');
      return HttpResponse.json([...stored.values()].filter((application) => application.company_id === companyId).reverse().map(({ id, number, state, stage, product_code, amount, awaiting_signature, updated_at }) => ({ id, number, state, stage, product_code, amount, awaiting_signature, updated_at })));
    }),
    http.post<EmptyParams, Schema['ApplicationCreate'], Application | ApiError>('*/api/v1/applications', async ({ request }) => {
      const me = account(request);
      if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
      const body = await request.json();
      if (!ownsCompany(me, body.company_id)) return error(403, 'FORBIDDEN', 'Нет доступа к этой компании.');
      const product = products.find(({ code }) => code === body.product_code);
      const fields: Record<string, string> = {};
      if (!product) fields.product_code = 'Выберите продукт.';
      if (!Number.isInteger(body.amount) || !product || body.amount < product.min_amount || body.amount > product.max_amount) fields.amount = 'Укажите целую сумму в пределах продукта.';
      if (!Number.isInteger(body.term_months) || !product || body.term_months < product.min_term_months || body.term_months > product.max_term_months) fields.term_months = 'Выберите срок в пределах продукта.';
      if (!Number.isInteger(body.declared_revenue_year) || body.declared_revenue_year <= 0) fields.declared_revenue_year = 'Укажите выручку за год в целых рублях.';
      if (!product?.purposes.includes(body.purpose)) fields.purpose = 'Выберите цель кредита.';
      if (body.purpose === 'OTHER' && (!body.purpose_text || body.purpose_text.length < 10 || body.purpose_text.length > 500)) fields.purpose_text = 'Опишите цель: от 10 до 500 символов.';
      if (Object.keys(fields).length) return error(422, 'VALIDATION_ERROR', 'Проверьте поля заявки.', fields);
      const application = draftApplication(body, crypto.randomUUID(), 1001 + stored.size);
      stored.set(application.id, application);
      return HttpResponse.json(application, { status: 201 });
    }),
    http.get<{ id: string }, never, Application | ApiError>('*/api/v1/applications/:id', ({ request, params }) => {
      const me = account(request);
      if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
      const application = stored.get(params.id) ?? applicationScenarios.find((item) => item.id === params.id);
      if (!application) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      if (!ownsCompany(me, application.company_id)) return error(403, 'FORBIDDEN', 'Нет доступа к этой заявке.');
      return HttpResponse.json(application);
    }),
    http.post<{ id: string }, never, Application | ApiError>('*/api/v1/applications/:id/withdraw', ({ request, params }) => {
      const me = account(request);
      if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
      const application = stored.get(params.id) ?? applicationScenarios.find((item) => item.id === params.id);
      if (!application || !ownsCompany(me, application.company_id)) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      if (!me.companies.find(({ company }) => company.id === application.company_id)?.can_sign) return error(403, 'SIGN_NOT_ALLOWED', 'Отозвать заявку может сотрудник с правом подписи.');
      if (!application.allowed_actions.includes('WITHDRAW')) return error(409, 'INVALID_TRANSITION', 'Заявка уже изменилась.');
      const now = new Date().toISOString();
      const updated: Application = { ...application, version: application.version + 1, state: 'WITHDRAWN', updated_at: now,
        stage: { ...application.stage, what_happens: 'Заявка отозвана', what_to_do: 'Можно подать новую заявку' },
        timeline: application.timeline.map((step) => step.stage_code === application.stage.code ? { ...step, status: 'cancelled', at: now } : step),
        allowed_actions: ['NEW_APPLICATION'],
      };
      stored.set(updated.id, updated);
      return HttpResponse.json(updated);
    }),
  ];
}
