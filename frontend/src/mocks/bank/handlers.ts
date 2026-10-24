import { http, HttpResponse } from 'msw';
import type { components } from '../../api/schema';
import { accounts, products } from '../fixtures';
import { bankApplications } from './fixtures';

type Schema = components['schemas'];
type App = Schema['ApplicationBank'];
const outcomes = ['APPROVE', 'COUNTER', 'DECLINE', 'REQUEST_INFO', 'RETRY_ENRICHMENT'];
const categories = ['Данные о компании', 'Финансовое положение', 'Срок ведения бизнеса', 'Кредитная история', 'Налоги и обязательства', 'Условия продукта', 'Дополнительные проверки', 'Финансовые показатели', 'Долговая нагрузка'];
function error(status: number, code: Schema['ApiError']['error']['code'], message: string, fields?: Record<string, string>) {
  return HttpResponse.json<Schema['ApiError']>({ error: { code, message, details: fields ? { fields } : {} } }, { status });
}
function access(request: Request) {
  const token = request.headers.get('Authorization');
  const me = token?.startsWith('Bearer demo:') ? accounts[token.slice(12)] : undefined;
  if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
  if (me.user.role !== 'UNDERWRITER') return error(403, 'FORBIDDEN', 'Экран доступен специалисту банка.');
  return null;
}

export function createBankHandlers() {
  const stored = new Map(structuredClone(bankApplications).map(app => [app.id, app]));
  return [
    http.get('*/api/v1/underwriting/queue', ({ request }) => {
      const denied = access(request); if (denied) return denied;
      const queue: Schema['QueueItem'][] = [...stored.values()].filter(app => app.state === 'MANUAL_REVIEW').map(app => {
        const decision = app.decisions.find(d => d.kind === 'AUTO');
        return { id: app.id, number: app.number, company_name: app.company.name, company_kind: app.company.kind, product_code: app.product_code, amount: app.amount, grade: decision?.grade ?? null, route_reason: decision?.route_reason ?? 'GRADE_C', waiting_since: app.updated_at };
      }).sort((a, b) => a.waiting_since.localeCompare(b.waiting_since));
      return HttpResponse.json(queue);
    }),
    http.get<{ id: string }>('*/api/v1/underwriting/applications/:id', ({ request, params }) => {
      const denied = access(request); if (denied) return denied;
      const app = stored.get(params.id);
      return app ? HttpResponse.json(app) : error(404, 'NOT_FOUND', 'Заявка не найдена.');
    }),
    http.post<{ id: string }, Schema['UnderwriterDecisionRequest']>('*/api/v1/underwriting/:id/decision', async ({ request, params }) => {
      const denied = access(request); if (denied) return denied;
      const app = stored.get(params.id);
      if (!app) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      if (app.state !== 'MANUAL_REVIEW') return error(409, 'INVALID_TRANSITION', 'Заявка уже не на рассмотрении');
      let input: unknown;
      try { input = await request.json(); } catch { return error(422, 'VALIDATION_ERROR', 'Проверьте решение.', { outcome: 'Некорректный запрос' }); }
      if (!input || typeof input !== 'object' || Array.isArray(input)) return error(422, 'VALIDATION_ERROR', 'Проверьте решение.', { outcome: 'Некорректный запрос' });
      const fields: Record<string, string> = {};
      for (const key of Object.keys(input)) if (!['outcome', 'amount', 'term_months', 'client_reason_category', 'info_questions', 'comment'].includes(key)) fields[key] = 'Неизвестное поле';
      const body = input as Schema['UnderwriterDecisionRequest'];
      const product = products.find(p => p.code === app.product_code)!;
      if (!outcomes.includes(body.outcome)) fields.outcome = 'Выберите решение';
      if (typeof body.comment !== 'string' || body.comment.trim().length < 5 || body.comment.length > 2000) fields.comment = 'Комментарий: от 5 до 2000 символов';
      if (body.outcome === 'APPROVE' || body.outcome === 'COUNTER') {
        if (typeof body.amount !== 'number' || !Number.isInteger(body.amount) || body.amount < product.min_amount || body.amount > product.max_amount) fields.amount = 'Сумма должна быть целой и в границах продукта';
        if (typeof body.term_months !== 'number' || !Number.isInteger(body.term_months) || body.term_months < product.min_term_months || body.term_months > product.max_term_months) fields.term_months = 'Срок должен быть в границах продукта';
        if (body.outcome === 'APPROVE' && body.amount !== app.amount) fields.amount = 'Для одобрения сумма должна совпадать с заявкой';
        if (body.outcome === 'APPROVE' && body.term_months !== app.term_months) fields.term_months = 'Для одобрения срок должен совпадать с заявкой';
        if (body.outcome === 'COUNTER' && body.amount === app.amount && body.term_months === app.term_months) fields.amount = 'Встречное предложение должно отличаться от заявки по сумме или сроку';
      }
      if (body.outcome === 'DECLINE' && !categories.includes(body.client_reason_category ?? '')) fields.client_reason_category = 'Выберите категорию причины';
      if (body.outcome === 'REQUEST_INFO' && (!Array.isArray(body.info_questions) || body.info_questions.length < 1 || body.info_questions.length > 5 || body.info_questions.some(q => typeof q !== 'string' || q.trim().length < 5 || q.length > 500))) fields.info_questions = 'Нужны 1–5 вопросов по 5–500 символов';
      if (Object.keys(fields).length) return error(422, 'VALIDATION_ERROR', 'Проверьте поля решения.', fields);
      const auto = app.decisions.find(d => d.kind === 'AUTO');
      if (body.outcome === 'RETRY_ENRICHMENT' && auto?.route_reason !== 'SOURCE_UNAVAILABLE') return error(409, 'INVALID_TRANSITION', 'Повторный сбор здесь недоступен');
      const now = new Date().toISOString();
      const state: App['state'] = body.outcome === 'DECLINE' ? 'DECLINED' : body.outcome === 'REQUEST_INFO' ? 'INFO_REQUESTED' : body.outcome === 'RETRY_ENRICHMENT' ? 'ENRICHMENT' : 'OFFER_ISSUED';
      const recommendation = auto?.recommendation;
      const override = !recommendation || body.outcome !== recommendation.outcome || ((body.outcome === 'APPROVE' || body.outcome === 'COUNTER') && (body.amount !== recommendation.amount || body.term_months !== recommendation.term_months));
      const manual: Schema['DecisionBank'] = { ...auto!, id: crypto.randomUUID(), kind: 'MANUAL', outcome: body.outcome, made_by: accounts.underwriter!.user.full_name, comment: body.comment, created_at: now, client_reason_code: body.outcome === 'DECLINE' ? 'UNDERWRITER_DECLINE' : null, factors: [], rules_fired: [], internal_reasons: [] };
      const retry = state === 'ENRICHMENT';
      const info = state === 'INFO_REQUESTED';
      const stage: App['stage'] = { index: retry ? 2 : 4, code: retry ? 'CHECK' : 'DECISION', title: retry ? 'Проверка данных' : 'Решение', what_happens: retry ? 'Повторно собираем сведения' : info ? 'Запрошены дополнительные данные' : state === 'DECLINED' ? 'По заявке принято решение' : 'Предложение направлено клиенту', what_to_do: info ? 'Ответьте на вопросы банка' : null };
      const updated: App = { ...app, state, stage, version: app.version + 1, updated_at: now,
        decisions: [manual, ...app.decisions],
        timeline: app.timeline.map((step, i) => ({ ...step, status: i < stage.index - 1 ? 'done' : i === stage.index - 1 ? state === 'DECLINED' ? 'failed' : info || state === 'OFFER_ISSUED' ? 'action_required' : 'current' : 'pending', at: i < stage.index - 1 || state === 'DECLINED' && i === 3 ? now : null })),
        allowed_actions: info ? ['ANSWER_INFO_REQUEST', 'WITHDRAW'] : state === 'OFFER_ISSUED' ? ['ACCEPT_OFFER', 'REJECT_OFFER', 'WITHDRAW'] : state === 'DECLINED' ? ['NEW_APPLICATION'] : ['WITHDRAW'],
        info_request: info ? { id: crypto.randomUUID(), due_at: new Date(Date.now() + 7 * 86400000).toISOString(), items: body.info_questions!.map(question => ({ item_code: 'UNDERWRITER_QUESTION', question, requires_value: false })) } : null,
        client_reason: state === 'DECLINED' ? { code: 'UNDERWRITER_DECLINE', category: body.client_reason_category!, text: 'Заявка не одобрена специалистом банка', action: null, retry_after: null } : null,
        offer: state === 'OFFER_ISSUED' ? { id: crypto.randomUUID(), version: 1, kind: body.outcome === 'COUNTER' ? 'COUNTER' : 'APPROVED', status: 'ACTIVE', product_code: app.product_code, amount: body.amount!, term_months: body.term_months!, rate: auto?.policy?.rate ?? recommendation?.rate ?? product.rate_from, monthly_payment: null, expires_at: new Date(Date.now() + 7 * 86400000).toISOString(), explanation: ['Решение принято специалистом банка'], requested: body.outcome === 'COUNTER' ? { amount: app.amount, term_months: app.term_months } : null, counter_reason: body.outcome === 'COUNTER' ? 'Предложены другие условия' : null } : null,
        events: [...app.events, { at: now, event_type: 'DECISION_MADE', from_state: app.state, to_state: state, actor: manual.made_by!, reason_code: manual.client_reason_code, note: body.comment }, ...(override ? [{ at: now, event_type: 'UNDERWRITER_OVERRIDE', from_state: null, to_state: null, actor: manual.made_by!, reason_code: null, note: 'Решение не совпадает с рекомендацией' }] : [])],
      };
      if (updated.offer && app.product_code !== 'OVERDRAFT') { const r = updated.offer.rate / 1200; updated.offer.monthly_payment = r === 0 ? Math.round(updated.offer.amount / updated.offer.term_months) : Math.round(updated.offer.amount * r / (1 - (1 + r) ** -updated.offer.term_months)); }
      stored.set(app.id, updated);
      return HttpResponse.json(updated);
    }),
  ];
}
