import { http, HttpResponse } from 'msw';
import type { components } from '../../api/schema';
import { accounts } from '../fixtures';
import { bankApplications } from './fixtures';

type Schema = components['schemas'];
type App = Schema['ApplicationBank'];
type State = App['state'];
const states: State[] = ['OFFER_ISSUED', 'SIGNING', 'INFO_REQUESTED', 'DRAFT', 'SUBMITTED', 'VALIDATION', 'ENRICHMENT', 'ASSESSMENT', 'MANUAL_REVIEW', 'DECLINED', 'SIGNED', 'DISBURSED', 'WITHDRAWN', 'EXPIRED'];
const stages: { code: App['stage']['code']; title: string; states: State[] }[] = [
  { code: 'APPLICATION', title: 'Заявка', states: ['DRAFT', 'SUBMITTED'] },
  { code: 'CHECK', title: 'Проверка данных', states: ['VALIDATION', 'ENRICHMENT', 'INFO_REQUESTED'] },
  { code: 'ASSESSMENT', title: 'Оценка', states: ['ASSESSMENT', 'MANUAL_REVIEW'] },
  { code: 'DECISION', title: 'Решение', states: ['OFFER_ISSUED', 'DECLINED', 'WITHDRAWN', 'EXPIRED'] },
  { code: 'SIGNING', title: 'Подписание', states: ['SIGNING', 'SIGNED'] },
  { code: 'DISBURSEMENT', title: 'Выдача', states: ['DISBURSED'] },
];
const names = ['ООО «Маяк»', 'ИП Смирнова Анна', 'ООО «Мастерская»', 'ООО «Горизонт»', 'ИП Орлов Павел', 'ООО «Пекарня у дома»', 'ООО «Логистика Плюс»'];
function background(index: number): App {
  const base = structuredClone(bankApplications[0]!);
  // Ручные заявки берём из F-07: его обработчик решения владеет только своими id.
  const backgroundStates = states.filter(value => value !== 'MANUAL_REVIEW');
  const state = backgroundStates[index % backgroundStates.length]!;
  const id = `journal-${index + 1}`;
  const kind = index % 7 === 1 || index % 7 === 4 ? 'IP' : 'OOO';
  const stageIndex = stages.findIndex(stage => stage.states.includes(state));
  const stage = stages[stageIndex]!;
  const now = new Date();
  const expires = (days: number) => new Date(now.getTime() + days * 86400000).toISOString();
  const early = ['DRAFT', 'SUBMITTED', 'VALIDATION', 'ENRICHMENT', 'INFO_REQUESTED', 'ASSESSMENT'].includes(state);
  const offered = ['OFFER_ISSUED', 'SIGNING', 'SIGNED', 'DISBURSED'].includes(state);
  return { ...base, id, number: 1101 + index, company_id: `company-${id}`, state,
    company: { ...base.company, id: `company-${id}`, name: names[index % names.length]!, kind, inn: kind === 'IP' ? `5001000000${String(index).padStart(2, '0')}` : `77050000${String(index).padStart(2, '0')}`, ogrn: kind === 'IP' ? `3265001000000${String(index).padStart(2, '0')}` : `12677000000${String(index).padStart(2, '0')}` },
    stage: { index: (stageIndex + 1) as App['stage']['index'], code: stage.code, title: stage.title, what_happens: 'Демонстрационная заявка', what_to_do: null },
    timeline: stages.map((s, i) => ({ stage_code: s.code, title: s.title, status: i < stageIndex ? 'done' : i === stageIndex ? 'current' : 'pending', at: i <= stageIndex ? base.updated_at : null })),
    decisions: early ? [] : base.decisions.map(d => ({ ...d, id: `auto-${id}`, outcome: offered ? 'APPROVE' : state === 'DECLINED' ? 'DECLINE' : d.outcome, route_reason: null })),
    offer: offered ? { id: `offer-${id}`, version: 1, kind: 'APPROVED', status: state === 'OFFER_ISSUED' ? 'ACTIVE' : 'ACCEPTED', product_code: base.product_code, amount: base.amount, term_months: base.term_months, rate: 26, monthly_payment: 53875, expires_at: expires(30), explanation: ['Компания прошла проверку'], requested: null, counter_reason: null } : null,
    info_request: state === 'INFO_REQUESTED' ? { id: `info-${id}`, items: [{ item_code: 'REVENUE_CONFIRM', question: 'Подтвердите поступления', requires_value: true }], due_at: expires(5) } : null,
    client_reason: null, allowed_actions: [],
    events: [{ at: base.created_at, event_type: 'STATE_CHANGED', from_state: null, to_state: 'DRAFT', actor: 'Клиент', reason_code: null, note: 'Заявка создана' }, ...(state === 'DRAFT' ? [] : [{ at: base.updated_at, event_type: 'STATE_CHANGED', from_state: 'DRAFT' as const, to_state: state, actor: 'Система', reason_code: null, note: 'Демонстрационная история заявки' }])],
  };
}
function error(status: number, code: Schema['ApiError']['error']['code'], message: string, fields?: Record<string, string>) {
  return HttpResponse.json<Schema['ApiError']>({ error: { code, message, details: fields ? { fields } : {} } }, { status });
}
function access(request: Request) {
  const token = request.headers.get('Authorization');
  const me = token?.startsWith('Bearer demo:') ? accounts[token.slice(12)] : undefined;
  if (!me) return error(401, 'UNAUTHORIZED', 'Войдите в кабинет.');
  return me.user.role === 'UNDERWRITER' ? null : error(403, 'FORBIDDEN', 'Экран доступен специалисту банка.');
}
export function createJournalHandlers() {
  // TODO(lead): общий store с F-07 нужен для отражения ручных решений; его приватный store в bank/handlers.ts вне F-08.
  const reused = structuredClone(bankApplications);
  const own = new Map(Array.from({ length: 21 }, (_, i) => background(i)).map(app => [app.id, app]));
  const shifted = new Map<string, number>();
  const applications = () => [...reused, ...own.values()];
  return [
    http.get('*/api/v1/bank/applications', ({ request }) => {
      const denied = access(request); if (denied) return denied;
      const query = new URL(request.url).searchParams;
      const state = query.get('state');
      const page = Number(query.get('page') ?? 1);
      const size = Number(query.get('size') ?? 20);
      const fields: Record<string, string> = {};
      if (!Number.isInteger(page) || page < 1) fields.page = 'Страница — целое число от 1';
      if (!Number.isInteger(size) || size < 1 || size > 100) fields.size = 'Размер страницы — от 1 до 100';
      if (state && !states.includes(state as State)) fields.state = 'Неизвестное состояние';
      if (Object.keys(fields).length) return error(422, 'VALIDATION_ERROR', 'Проверьте фильтр.', fields);
      const filtered = applications().filter(app => !state || app.state === state);
      const items: Schema['BankListItem'][] = filtered.slice((page - 1) * size, page * size).map(app => {
        const auto = app.decisions.find(d => d.kind === 'AUTO');
        return { id: app.id, number: app.number, company_name: app.company.name, company_kind: app.company.kind, product_code: app.product_code, amount: app.amount, grade: auto?.grade ?? null, route_reason: auto?.route_reason ?? 'GRADE_C', waiting_since: app.updated_at, updated_at: app.updated_at, state: app.state };
      });
      return HttpResponse.json({ items, total: filtered.length, page, size });
    }),
    http.get<{ id: string }>('*/api/v1/underwriting/applications/:id', ({ request, params }) => {
      const app = own.get(params.id);
      if (!app) return undefined;
      const denied = access(request); if (denied) return denied;
      return HttpResponse.json(app);
    }),
    http.post<Record<string, string>, Schema['TimeShiftRequest'], Schema['TimeShiftResponse'] | Schema['ApiError']>('*/api/v1/demo/time-shift', async ({ request }) => {
      const denied = access(request); if (denied) return denied;
      let input: unknown;
      try { input = await request.json(); } catch { return error(422, 'VALIDATION_ERROR', 'Проверьте поля.', { days: 'Некорректный запрос' }); }
      if (!input || typeof input !== 'object' || Array.isArray(input)) return error(422, 'VALIDATION_ERROR', 'Проверьте поля.', { days: 'Некорректный запрос' });
      const body = input as Record<string, unknown>;
      const fields: Record<string, string> = {};
      for (const key of Object.keys(body)) if (!['application_id', 'days'].includes(key)) fields[key] = 'Неизвестное поле';
      if (typeof body.application_id !== 'string' || !body.application_id) fields.application_id = 'Укажите заявку';
      if (typeof body.days !== 'number' || !Number.isInteger(body.days) || body.days < 1 || body.days > 400) fields.days = 'Введите целое число от 1 до 400';
      if (Object.keys(fields).length) return error(422, 'VALIDATION_ERROR', 'Проверьте поля.', fields);
      const { application_id: id, days } = body as unknown as Schema['TimeShiftRequest'];
      const app = own.get(id) ?? reused.find(item => item.id === id);
      if (!app) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      const total = (shifted.get(id) ?? 0) + days;
      shifted.set(id, total);
      const before = app.state;
      const expired = before === 'INFO_REQUESTED' ? total >= 5 : ['OFFER_ISSUED', 'SIGNING'].includes(before) && total >= 30;
      const shift = (at: string) => new Date(new Date(at).getTime() - days * 86400000).toISOString();
      if (app.offer) app.offer.expires_at = shift(app.offer.expires_at);
      if (app.info_request) app.info_request.due_at = shift(app.info_request.due_at);
      if (expired) {
        app.state = 'EXPIRED'; app.updated_at = new Date().toISOString(); app.version++;
        app.stage = { ...app.stage, what_happens: 'Срок заявки истёк', what_to_do: 'Можно подать новую заявку' };
        app.timeline = app.timeline.map(step => step.stage_code === app.stage.code ? { ...step, status: 'cancelled', at: app.updated_at } : step);
        app.allowed_actions = ['NEW_APPLICATION'];
        if (app.offer) app.offer.status = 'EXPIRED';
        const reason = before === 'INFO_REQUESTED' ? 'EXPIRED_INFO' : 'EXPIRED_OFFER';
        app.client_reason = { code: reason, category: null, text: 'Срок заявки истёк', action: 'Можно подать новую заявку', retry_after: null };
        app.events.push({ at: app.updated_at, event_type: 'STATE_CHANGED', from_state: before, to_state: 'EXPIRED', actor: 'Система', reason_code: reason, note: 'Срок истёк после перемотки времени' });
      }
      return HttpResponse.json<Schema['TimeShiftResponse']>({ application_id: id, expired_now: expired, state: app.state });
    }),
  ];
}
