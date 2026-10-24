import { http, HttpResponse } from 'msw';
import type { components } from '../../api/schema';
import { accounts, applications, applicationScenarios } from '../fixtures';
import { enterSigning, signingView } from './signing';

type Schema = components['schemas'];
type Application = Schema['ApplicationClient'];
type ErrorCode = Schema['ApiError']['error']['code'];
type Params = { id: string };
function error(status: number, code: ErrorCode, message: string, fields?: Record<string, string>) {
  return HttpResponse.json<Schema['ApiError']>({ error: { code, message, details: fields ? { fields } : {} } }, { status });
}
function membership(request: Request, application: Application) {
  const token = request.headers.get('Authorization') ?? '';
  const me = token.startsWith('Bearer demo:') ? accounts[token.slice('Bearer demo:'.length)] : undefined;
  return me?.user.role === 'CLIENT' ? me.companies.find(({ company }) => company.id === application.company_id) : undefined;
}
function view(request: Request, application: Application): Application {
  if (membership(request, application)?.can_sign) return application;
  const unsigned = ['ACCEPT_OFFER', 'REJECT_OFFER', 'WITHDRAW'];
  return { ...application, allowed_actions: application.allowed_actions.filter((action) => !unsigned.includes(action)),
    ...(application.state === 'OFFER_ISSUED' ? { stage: { ...application.stage, what_to_do: 'Ждём решения подписанта компании' }, timeline: application.timeline.map((step) => step.stage_code === application.stage.code ? { ...step, status: 'current' as const } : step) } : {}),
  };
}
function move(application: Application, state: Application['state'], index: Schema['Stage']['index'], status: Schema['TimelineItem']['status'], what_happens: string, what_to_do: string | null, allowed_actions: Application['allowed_actions']): Application {
  const now = new Date().toISOString();
  const step = application.timeline[index - 1]!;
  return { ...application, version: application.version + 1, updated_at: now, state,
    stage: { index, code: step.stage_code, title: step.title, what_happens, what_to_do },
    timeline: application.timeline.map((item, position) => ({ ...item, status: position < index - 1 ? 'done' : position === index - 1 ? status : 'pending', at: position < index ? item.at ?? now : null })), allowed_actions,
  };
}
// The shared map keeps F-03 drafts and F-04 withdrawal consistent with F-05 actions.
export function createDecisionHandlers(stored = new Map<string, Application>()) {
  for (const application of applications) if (!stored.has(application.id)) stored.set(application.id, structuredClone(application));
  const scenarios = new Map(applicationScenarios.map((application) => [application.id, application]));
  function access(request: Request, id: string) {
    const application = stored.get(id) ?? scenarios.get(id);
    return application && membership(request, application) ? application : null;
  }
  return [
    http.get<Params>('*/api/v1/applications/:id', ({ request, params }) => {
      const application = access(request, params.id);
      return application ? HttpResponse.json(['DRAFT', 'SIGNING', 'SIGNED', 'DISBURSED'].includes(application.state) ? signingView(request, application) : view(request, application)) : undefined;
    }),
    http.post<Params, Schema['AcceptOfferRequest']>('*/api/v1/applications/:id/offer/accept', async ({ request, params }) => {
      const application = access(request, params.id);
      if (!application) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      if (!membership(request, application)?.can_sign) return error(403, 'SIGN_NOT_ALLOWED', 'Принять предложение может сотрудник с правом подписи.');
      const offer = application.offer;
      if (offer?.status === 'EXPIRED') return error(409, 'OFFER_EXPIRED', 'Срок предложения истёк');
      if (application.state !== 'OFFER_ISSUED' || offer?.status !== 'ACTIVE') return error(409, 'INVALID_TRANSITION', 'Предложение уже закрыто.');
      const body = await request.json();
      if (body.offer_version !== offer.version) return error(409, 'CONFLICT_VERSION', 'Условия изменились — проверьте их ещё раз');
      const updated = enterSigning(application);
      stored.set(updated.id, updated);
      return HttpResponse.json(signingView(request, updated));
    }),
    http.post<Params>('*/api/v1/applications/:id/offer/reject', ({ request, params }) => {
      const application = access(request, params.id);
      if (!application) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      if (!view(request, application).allowed_actions.includes('REJECT_OFFER')) return error(403, 'FORBIDDEN', 'Отказаться от предложения может сотрудник с правом подписи.');
      if (application.state !== 'OFFER_ISSUED' || application.offer?.status !== 'ACTIVE') return error(409, 'INVALID_TRANSITION', 'Предложение уже закрыто.');
      const updated = { ...move(application, 'WITHDRAWN', 4, 'cancelled', 'Вы отказались от предложения', 'Можно подать новую заявку', ['NEW_APPLICATION']), offer: { ...application.offer, status: 'REJECTED' as const }, client_reason: { code: 'CLIENT_REJECTED_OFFER', category: null, text: 'Вы отказались от предложения банка', action: 'Можно подать новую заявку', retry_after: null } };
      updated.timeline[3]!.at = updated.updated_at;
      stored.set(updated.id, updated);
      return HttpResponse.json(updated);
    }),
    http.post<Params, Schema['ObjectionRequest']>('*/api/v1/applications/:id/objection', async ({ request, params }) => {
      const application = access(request, params.id);
      if (!application) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      if (!application.allowed_actions.includes('OBJECT') || application.state !== 'DECLINED') return error(403, 'OBJECTION_NOT_ALLOWED', 'Пересмотр сейчас недоступен.');
      const body = await request.json();
      if (typeof body.text !== 'string' || body.text.trim().length < 10 || body.text.length > 2000) return error(422, 'VALIDATION_ERROR', 'Проверьте обращение.', { text: 'Введите от 10 до 2000 символов' });
      const updated: Application = { ...move(application, 'MANUAL_REVIEW', 3, 'current', 'Заявку рассматривает специалист банка — обычно до 1 рабочего дня', null, ['WITHDRAW']), client_reason: null, objection: { status: 'PENDING', created_at: new Date().toISOString(), outcome_text: null } };
      stored.set(updated.id, updated);
      return HttpResponse.json(view(request, updated));
    }),
    http.post<Params, Schema['InfoResponseRequest']>('*/api/v1/applications/:id/info-response', async ({ request, params }) => {
      const application = access(request, params.id);
      if (!application) return error(404, 'NOT_FOUND', 'Заявка не найдена.');
      const info = application.info_request;
      if (application.state !== 'INFO_REQUESTED' || !info) return error(409, 'INVALID_TRANSITION', 'Запрос уже закрыт');
      const body = await request.json();
      const fields: Record<string, string> = {};
      const remaining = [...info.items];
      const matched = Array.isArray(body.answers) ? body.answers.map((answer) => {
        const index = remaining.findIndex((item) => item.item_code === answer?.item_code);
        return index < 0 ? undefined : remaining.splice(index, 1)[0];
      }) : [];
      if (!Array.isArray(body.answers) || remaining.length || matched.some((item) => !item)) fields.answers = 'Ответьте ровно один раз на каждый вопрос банка';
      if (Array.isArray(body.answers)) for (const [index, answer] of body.answers.entries()) {
        const item = matched[index];
        if (typeof answer?.comment !== 'string' || answer.comment.trim().length < 3 || answer.comment.length > 1000) fields[`answers.${index}.comment`] = 'Введите от 3 до 1000 символов';
        if (item?.requires_value ? !Number.isSafeInteger(answer.value) || answer.value! <= 0 : answer?.value !== undefined) fields[`answers.${index}.value`] = 'Укажите целую выручку больше нуля';
      }
      if (Object.keys(fields).length) return error(422, 'VALIDATION_ERROR', 'Проверьте ответы.', fields);
      const updated = { ...move(application, 'VALIDATION', 2, 'current', 'Проверяем данные заявки', null, ['WITHDRAW']), info_request: null };
      stored.set(updated.id, updated);
      return HttpResponse.json(view(request, updated));
    }),
  ];
}
