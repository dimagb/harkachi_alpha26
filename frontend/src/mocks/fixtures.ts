import type { components } from '../api/schema';

type Schema = components['schemas'];

// Public data copied from contracts/personas.json (ip_good, ooo_load and staff).
// Internal scoring and source data are deliberately absent from browser fixtures.
export const accounts: Record<string, Schema['MeResponse']> = {
  ip_good: {
    user: { id: '10000000-0000-4000-8000-000000000001', full_name: 'Смирнова Анна Викторовна', role: 'CLIENT' },
    companies: [{ company: { id: '20000000-0000-4000-8000-000000000001', inn: '770112345695', kind: 'IP', name: 'ИП Смирнова Анна Викторовна' }, position: 'Индивидуальный предприниматель', can_sign: true, is_founder: true }],
  },
  ooo_load: {
    user: { id: '10000000-0000-4000-8000-000000000002', full_name: 'Петров Илья Игоревич', role: 'CLIENT' },
    companies: [{ company: { id: '20000000-0000-4000-8000-000000000002', inn: '7702123454', kind: 'OOO', name: 'ООО «Северный склад»' }, position: 'Генеральный директор', can_sign: true, is_founder: true }],
  },
  underwriter: {
    user: { id: '10000000-0000-4000-8000-000000000003', full_name: 'Орлова Мария Андреевна', role: 'UNDERWRITER' },
    companies: [],
  },
};

const at = '2026-10-23T09:00:00Z';
const draftStage: Schema['Stage'] = { index: 1, code: 'APPLICATION', title: 'Заявка', what_happens: 'Заявка сохранена как черновик.', what_to_do: 'Заполните и отправьте заявку.' };

export function draftApplication(body: Schema['ApplicationCreate'], id: string, number: number): Schema['ApplicationClient'] {
  const now = new Date().toISOString();
  return {
    ...body, purpose_text: body.purpose_text ?? null, id, number, version: 1, state: 'DRAFT',
    stage: draftStage,
    timeline: [
      { stage_code: 'APPLICATION', title: 'Заявка', status: 'current', at: null },
      { stage_code: 'CHECK', title: 'Проверка', status: 'pending', at: null },
      { stage_code: 'ASSESSMENT', title: 'Оценка', status: 'pending', at: null },
      { stage_code: 'DECISION', title: 'Решение', status: 'pending', at: null },
      { stage_code: 'SIGNING', title: 'Подписание', status: 'pending', at: null },
      { stage_code: 'DISBURSEMENT', title: 'Выдача', status: 'pending', at: null },
    ],
    offer: null, client_reason: null, info_request: null, parties: [],
    allowed_actions: ['EDIT_DRAFT', 'SUBMIT', 'WITHDRAW'], awaiting_signature: false, objection: null,
    created_at: now, updated_at: now,
  };
}

function offeredApplication(body: Schema['ApplicationCreate'], id: string, number: number, offer: Schema['OfferClient']): Schema['ApplicationClient'] {
  const draft = draftApplication(body, id, number);
  return {
    ...draft, state: 'OFFER_ISSUED', created_at: at, updated_at: at,
    stage: { index: 4, code: 'DECISION', title: 'Решение', what_happens: 'Для вас подготовлено предложение.', what_to_do: 'Ознакомьтесь с условиями предложения.' },
    timeline: draft.timeline.map((step, index) => ({ ...step, status: index < 3 ? 'done' : index === 3 ? 'action_required' : 'pending', at: index < 4 ? at : null })),
    offer, allowed_actions: ['ACCEPT_OFFER', 'REJECT_OFFER', 'WITHDRAW'],
  };
}

export const applications: Schema['ApplicationClient'][] = [
  offeredApplication(
    { company_id: '20000000-0000-4000-8000-000000000001', product_code: 'EXPRESS', amount: 1500000, term_months: 24, purpose: 'WORKING_CAPITAL', declared_revenue_year: 14000000 },
    '30000000-0000-4000-8000-000000000001', 1001,
    { id: '40000000-0000-4000-8000-000000000001', version: 1, kind: 'APPROVED', status: 'ACTIVE', product_code: 'EXPRESS', amount: 1500000, term_months: 24, rate: 22.00, monthly_payment: 77817, expires_at: '2026-10-30T09:00:00Z', explanation: ['Предложение на запрошенную сумму.'], requested: null, counter_reason: null },
  ),
  offeredApplication(
    { company_id: '20000000-0000-4000-8000-000000000002', product_code: 'WORKING_CAPITAL', amount: 4000000, term_months: 12, purpose: 'WORKING_CAPITAL', declared_revenue_year: 24000000 },
    '30000000-0000-4000-8000-000000000002', 1002,
    { id: '40000000-0000-4000-8000-000000000002', version: 1, kind: 'COUNTER', status: 'ACTIVE', product_code: 'WORKING_CAPITAL', amount: 2850000, term_months: 24, rate: 23.00, monthly_payment: 149264, expires_at: '2026-10-30T09:00:00Z', explanation: ['Подобраны сумма и срок с учётом текущих обязательств.'], requested: { amount: 4000000, term_months: 12 }, counter_reason: 'Предлагаем меньшую сумму на более длительный срок, чтобы снизить платёж.' },
  ),
];

// Catalog: docs/TASKS.md F-01 and the product showcase in contracts/codes.md.
export const products: Schema['Product'][] = [
  { code: 'EXPRESS', name: 'Экспресс-кредит', description: 'На любые цели бизнеса', purposes: ['WORKING_CAPITAL', 'CASH_GAP', 'EQUIPMENT', 'OTHER'], min_amount: 300000, max_amount: 5000000, min_term_months: 6, max_term_months: 36, rate_from: 22.00, requires_guarantor_ooo: true, key_rate: 14.00, key_rate_date: '2026-10-23' },
  { code: 'WORKING_CAPITAL', name: 'Оборотный кредит', description: 'На пополнение оборотных средств', purposes: ['WORKING_CAPITAL', 'CASH_GAP'], min_amount: 500000, max_amount: 15000000, min_term_months: 3, max_term_months: 24, rate_from: 21.00, requires_guarantor_ooo: true, key_rate: 14.00, key_rate_date: '2026-10-23' },
  { code: 'OVERDRAFT', name: 'Овердрафт', description: 'На покрытие кассовых разрывов', purposes: ['CASH_GAP', 'WORKING_CAPITAL'], min_amount: 100000, max_amount: 5000000, min_term_months: 12, max_term_months: 12, rate_from: 24.00, requires_guarantor_ooo: true, key_rate: 14.00, key_rate_date: '2026-10-23' },
];
