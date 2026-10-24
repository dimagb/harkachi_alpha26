import { http, HttpResponse } from 'msw';
import type { components } from '../../api/schema';
import { accounts, applicationScenarios } from '../fixtures';

type Schema = components['schemas'];
type Application = Schema['ApplicationClient'];
type Params = { id: string };
type Code = { applicationId: string; userId: string; purpose: Schema['OtpRequest']['purpose']; partyId?: string; code: string; expiresAt: number };
function error(status: number, code: Schema['ApiError']['error']['code'], message: string) {
  return HttpResponse.json<Schema['ApiError']>({ error: { code, message, details: {} } }, { status });
}
function move(application: Application, state: 'SUBMITTED' | 'SIGNED' | 'DISBURSED'): Application {
  const index = state === 'SUBMITTED' ? 1 : state === 'SIGNED' ? 5 : 6;
  const now = new Date().toISOString();
  return { ...application, state, version: application.version + 1, updated_at: now,
    stage: { index, code: application.timeline[index - 1]!.stage_code, title: application.timeline[index - 1]!.title, what_happens: state === 'SUBMITTED' ? 'Заявка отправлена, скоро начнём проверку' : state === 'SIGNED' ? 'Договор подписан, готовим выдачу' : 'Деньги зачислены на счёт', what_to_do: null },
    timeline: application.timeline.map((step, i) => ({ ...step, status: i < index - 1 || state === 'DISBURSED' ? 'done' : i === index - 1 ? 'current' : 'pending', at: i < index ? step.at ?? now : null })),
    allowed_actions: state === 'SUBMITTED' ? ['WITHDRAW'] : state === 'DISBURSED' ? ['NEW_APPLICATION'] : [],
  };
}
function partyOwner(application: Application, party: Application['parties'][number]) {
  return party.is_me ? Object.values(accounts).find((account) => account.user.full_name === party.full_name && account.companies.some((member) => member.company.id === application.company_id && member.can_sign))?.user.id : undefined;
}
function projectSigning(application: Application, userId: string | undefined, canSign: boolean): Application {
  const parties = application.parties.map((party) => ({ ...party, is_me: !!userId && partyOwner(application, party) === userId }));
  if (application.state !== 'SIGNING') return { ...application, parties };
  const ownPending = parties.some((party) => party.is_me && !party.signed);
  return { ...application, parties, allowed_actions: [...(ownPending ? ['SIGN' as const] : []), ...(canSign ? ['WITHDRAW' as const] : [])],
    stage: { ...application.stage, what_to_do: ownPending ? 'Подпишите договор кодом подтверждения' : 'Ждём подписи остальных участников' },
    timeline: application.timeline.map((step) => step.stage_code === 'SIGNING' ? { ...step, status: ownPending ? 'action_required' : 'current' } : step),
  };
}
function projectDraft(application: Application, canSign: boolean): Application {
  if (canSign) return { ...application, allowed_actions: ['EDIT_DRAFT', 'SUBMIT', 'WITHDRAW'] };
  const needsAction = !application.awaiting_signature;
  return { ...application,
    stage: { ...application.stage, what_to_do: needsAction ? 'Отправьте заявку на подпись руководителю или сотруднику с правом подписи' : 'Ждём решения подписанта компании' },
    timeline: application.timeline.map((step) => step.stage_code === 'APPLICATION' ? { ...step, status: needsAction ? 'action_required' : 'current' } : step),
    allowed_actions: ['EDIT_DRAFT', ...(canSign ? ['SUBMIT' as const] : application.awaiting_signature ? [] : ['REQUEST_SIGNATURE' as const]), 'WITHDRAW'],
  };
}
export function signingView(request: Request, application: Application): Application {
  const token = request.headers.get('Authorization') ?? '';
  const me = token.startsWith('Bearer demo:') ? accounts[token.slice('Bearer demo:'.length)] : undefined;
  const member = me?.companies.find(({ company }) => company.id === application.company_id);
  if (application.state === 'DRAFT') return projectDraft(application, member?.can_sign ?? false);
  return projectSigning(application, me?.user.id, member?.can_sign ?? false);
}
export function enterSigning(application: Application): Application {
  const signer = Object.values(accounts).find((account) => account.companies.some((member) => member.company.id === application.company_id && member.can_sign));
  if (!signer) throw new Error('Демо-подписант не найден.');
  const company = signer.companies.find((member) => member.company.id === application.company_id)!.company;
  const roles = company.kind === 'OOO' ? ['BORROWER_SIGNATORY', 'GUARANTOR'] as const : ['BORROWER_SIGNATORY'] as const;
  const now = new Date().toISOString();
  return { ...application, state: 'SIGNING', version: application.version + 1, updated_at: now,
    offer: application.offer ? { ...application.offer, status: 'ACCEPTED' } : null,
    parties: application.parties.length ? application.parties : roles.map((role) => ({ id: crypto.randomUUID(), role, full_name: signer.user.full_name, signed: false, is_me: true })),
    stage: { index: 5, code: 'SIGNING', title: 'Подписание', what_happens: 'Готовим договор к подписанию', what_to_do: 'Подпишите договор кодом подтверждения' },
    timeline: application.timeline.map((step, index) => ({ ...step, status: index < 4 ? 'done' : index === 4 ? 'action_required' : 'pending', at: index < 5 ? step.at ?? now : null })),
    allowed_actions: ['SIGN', 'WITHDRAW'],
  };
}
export function createSigningHandlers(stored = new Map<string, Application>()) {
  const codes = new Map<string, Code>();
  const owners = new Map<string, string>();
  function me(request: Request) { return accounts[(request.headers.get('Authorization') ?? '').replace(/^Bearer demo:/, '')]; }
  function context(request: Request, id: string) {
    const user = me(request);
    if (!user) return { response: error(401, 'UNAUTHORIZED', 'Войдите в кабинет.') };
    const application = stored.get(id) ?? applicationScenarios.find((item) => item.id === id);
    const member = application && user.companies.find(({ company }) => company.id === application.company_id);
    if (!application || !member) return { response: error(404, 'NOT_FOUND', 'Заявка не найдена.') };
    for (const party of application.parties) if (!owners.has(party.id)) {
      const owner = party.is_me ? Object.values(accounts).find((account) => account.user.full_name === party.full_name && account.companies.some((m) => m.company.id === application.company_id && m.can_sign)) : undefined;
      if (owner) owners.set(party.id, owner.user.id);
    }
    return { application, user, member };
  }
  function view(application: Application, userId: string, canSign: boolean): Application {
    if (['SIGNING', 'SIGNED', 'DISBURSED'].includes(application.state)) return projectSigning(application, userId, canSign);
    if (application.state === 'DRAFT') return projectDraft(application, canSign);
    const parties = application.parties.map((party) => ({ ...party, is_me: owners.get(party.id) === userId }));
    return { ...application, parties, allowed_actions: !canSign && application.state === 'SUBMITTED' ? [] : application.allowed_actions };
  }
  function validCode(otpId: string, code: string, applicationId: string, userId: string, purpose: Code['purpose'], partyId?: string) {
    const otp = codes.get(otpId);
    return otp && otp.code === code && otp.applicationId === applicationId && otp.userId === userId && otp.purpose === purpose && otp.partyId === partyId && otp.expiresAt > Date.now();
  }
  return [
    http.get<Params>('*/api/v1/applications/:id', ({ request, params }) => {
      const ctx = context(request, params.id); if (ctx.response) return undefined;
      return HttpResponse.json(view(ctx.application!, ctx.user!.user.id, ctx.member!.can_sign));
    }),
    http.post<Params, Schema['OtpRequest']>('*/api/v1/applications/:id/otp', async ({ request, params }) => {
      const ctx = context(request, params.id); if (ctx.response) return ctx.response;
      const { application, user, member } = ctx;
      const body = await request.json();
      if (!body || !['CONSENTS', 'OFFER', 'GUARANTEE'].includes(body.purpose) || Object.keys(body).some((key) => !['purpose', 'party_id'].includes(key))) return error(422, 'VALIDATION_ERROR', 'Выберите назначение кода.');
      if (body.purpose === 'CONSENTS') {
        if (body.party_id !== undefined) return error(422, 'VALIDATION_ERROR', 'Для согласий участник не указывается.');
        if (!member!.can_sign) return error(403, 'SIGN_NOT_ALLOWED', 'Отправить заявку может сотрудник с правом подписи.');
        if (application!.state !== 'DRAFT') return error(409, 'INVALID_TRANSITION', 'Заявка уже отправлена.');
      } else {
        if (application!.state !== 'SIGNING') return error(409, 'INVALID_TRANSITION', 'Подписание сейчас недоступно.');
        if (!body.party_id) return error(422, 'VALIDATION_ERROR', 'Выберите участника подписи.');
        const party = application!.parties.find((p) => p.id === body.party_id);
        if (!party || owners.get(party.id) !== user!.user.id) return error(403, 'SIGN_NOT_ALLOWED', 'Вы можете подписать только за себя.');
        if (party.signed) return error(409, 'INVALID_TRANSITION', 'Подпись уже получена.');
        if (body.purpose !== (party.role === 'BORROWER_SIGNATORY' ? 'OFFER' : 'GUARANTEE')) return error(422, 'VALIDATION_ERROR', 'Назначение кода не соответствует участнику.');
      }
      for (const [id, previous] of codes) if (previous.applicationId === params.id && previous.userId === user!.user.id && previous.purpose === body.purpose && previous.partyId === body.party_id) codes.delete(id);
      const otp_id = crypto.randomUUID();
      const code = '123456'; const expiresAt = Date.now() + 300000;
      codes.set(otp_id, { applicationId: params.id, userId: user!.user.id, purpose: body.purpose, partyId: body.party_id, code, expiresAt });
      return HttpResponse.json<Schema['OtpResponse']>({ otp_id, demo_code: code, expires_at: new Date(expiresAt).toISOString() });
    }),
    http.post<Params, Schema['SubmitRequest']>('*/api/v1/applications/:id/submit', async ({ request, params }) => {
      const ctx = context(request, params.id); if (ctx.response) return ctx.response;
      const { application, member, user } = ctx;
      if (!member!.can_sign) return error(403, 'SIGN_NOT_ALLOWED', 'Отправить заявку может сотрудник с правом подписи.');
      if (application!.state !== 'DRAFT') return error(409, 'INVALID_TRANSITION', 'Заявка уже отправлена.');
      const body = await request.json();
      if (!body?.consents || body.consents.pdn !== true || body.consents.bki !== true || typeof body.consents.auto_decision !== 'boolean' || Object.keys(body).some((key) => !['otp_id', 'code', 'consents'].includes(key)) || Object.keys(body.consents).some((key) => !['pdn', 'bki', 'auto_decision'].includes(key))) return error(422, 'VALIDATION_ERROR', 'Подтвердите обязательные согласия.');
      if (!validCode(body.otp_id, body.code, params.id, user!.user.id, 'CONSENTS')) return error(422, 'OTP_INVALID', 'Код недействителен или истёк');
      codes.delete(body.otp_id);
      const roles = member!.company.kind === 'OOO' ? ['BORROWER_SIGNATORY', 'GUARANTOR'] as const : ['BORROWER_SIGNATORY'] as const;
      const parties = roles.map((role) => { const id = crypto.randomUUID(); owners.set(id, user!.user.id); return { id, role, full_name: user!.user.full_name, signed: false, is_me: true }; });
      const updated = { ...move(application!, 'SUBMITTED'), parties, awaiting_signature: false };
      stored.set(params.id, updated); return HttpResponse.json(view(updated, user!.user.id, member!.can_sign));
    }),
    http.post<Params>('*/api/v1/applications/:id/request-signature', ({ request, params }) => {
      const ctx = context(request, params.id); if (ctx.response) return ctx.response;
      const { application, member, user } = ctx;
      if (member!.can_sign) return error(403, 'SIGN_NOT_ALLOWED', 'Вы можете отправить заявку самостоятельно.');
      if (application!.state !== 'DRAFT') return error(409, 'INVALID_TRANSITION', 'Заявка уже отправлена.');
      const updated = application!.awaiting_signature ? application! : { ...application!, awaiting_signature: true, version: application!.version + 1, updated_at: new Date().toISOString() };
      stored.set(params.id, updated); return HttpResponse.json(view(updated, user!.user.id, member!.can_sign));
    }),
    http.post<Params, Schema['SignRequest']>('*/api/v1/applications/:id/sign', async ({ request, params }) => {
      const ctx = context(request, params.id); if (ctx.response) return ctx.response;
      const { application, member, user } = ctx;
      if (application!.state !== 'SIGNING') return error(409, 'INVALID_TRANSITION', 'Подписание сейчас недоступно.');
      const body = await request.json();
      if (!body || Object.keys(body).some((key) => !['otp_id', 'code', 'party_id'].includes(key))) return error(422, 'VALIDATION_ERROR', 'Проверьте данные подписи.');
      const party = application!.parties.find((p) => p.id === body.party_id);
      if (!party || owners.get(party.id) !== user!.user.id) return error(403, 'SIGN_NOT_ALLOWED', 'Вы можете подписать только за себя.');
      if (party.signed) return error(409, 'INVALID_TRANSITION', 'Подпись уже получена.');
      if (!validCode(body.otp_id, body.code, params.id, user!.user.id, party.role === 'BORROWER_SIGNATORY' ? 'OFFER' : 'GUARANTEE', party.id)) return error(422, 'OTP_INVALID', 'Код недействителен или истёк');
      codes.delete(body.otp_id);
      const parties = application!.parties.map((p) => p.id === party.id ? { ...p, signed: true } : p);
      const signed = { ...application!, parties, version: application!.version + 1, updated_at: new Date().toISOString() };
      const updated = parties.every((p) => p.signed) ? move(signed, 'SIGNED') : signed;
      stored.set(params.id, updated);
      if (updated.state === 'SIGNED') setTimeout(() => { if (stored.get(params.id)?.state === 'SIGNED') stored.set(params.id, move(stored.get(params.id)!, 'DISBURSED')); }, 2000);
      return HttpResponse.json(view(updated, user!.user.id, member!.can_sign));
    }),
  ];
}
