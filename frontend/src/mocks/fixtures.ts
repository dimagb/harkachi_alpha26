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

accounts.ooo_load_accountant = {
  user: { id: '10000000-0000-4000-8000-000000000004', full_name: 'Белова Ольга Сергеевна', role: 'CLIENT' },
  companies: accounts.ooo_load!.companies.map((membership) => ({ ...membership, position: 'Главный бухгалтер', can_sign: false, is_founder: false })),
};

// Public registry responses for the existing personas, checked against the local API.
export const companyProfiles: Record<string, Schema['CompanyProfile']> = {
  '20000000-0000-4000-8000-000000000001': {
    ...accounts.ip_good!.companies[0]!.company,
    ogrn: '322774600012345', status: 'ACTIVE', reg_date: '2022-09-01', okved_main: '56.10',
    address: 'г. Москва, ул. Покровка, д. 12', director_full_name: 'Смирнова Анна Викторовна', founders: [],
    avg_monthly_turnover: 1200000, source_note: 'Данные из ЕГРИП на 23.10.2026',
  },
  '20000000-0000-4000-8000-000000000002': {
    ...accounts.ooo_load!.companies[0]!.company,
    ogrn: '1237700012345', status: 'ACTIVE', reg_date: '2023-03-01', okved_main: '52.10',
    address: 'г. Москва, Складской пр., д. 4', director_full_name: 'Петров Илья Игоревич',
    founders: [{ full_name: 'Петров Илья Игоревич', share_pct: 100 }],
    avg_monthly_turnover: 2000000, source_note: 'Данные из ЕГРЮЛ на 23.10.2026',
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
    stage: { index: 4, code: 'DECISION', title: 'Решение', what_happens: 'Предложение готово', what_to_do: 'Примите предложение или откажитесь от него до указанного срока' },
    timeline: draft.timeline.map((step, index) => ({ ...step, title: index === 1 ? 'Проверка данных' : step.title, status: index < 3 ? 'done' : index === 3 ? 'action_required' : 'pending', at: index < 4 ? at : null })),
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

const scenarioStages: [Schema['ApplicationClient']['state'], Schema['Stage']['index'], Schema['TimelineItem']['status'], string, string | null, Schema['ApplicationClient']['allowed_actions']][] = [
  ['VALIDATION', 2, 'current', 'Проверяем данные заявки', null, ['WITHDRAW']],
  ['INFO_REQUESTED', 2, 'action_required', 'Нужно уточнить данные заявки', 'Ответьте на вопросы банка до указанного срока', ['ANSWER_INFO_REQUEST', 'WITHDRAW']],
  ['MANUAL_REVIEW', 3, 'current', 'Заявку рассматривает специалист банка — обычно до 1 рабочего дня', null, ['WITHDRAW']],
  ['OFFER_ISSUED', 4, 'action_required', 'Предложение готово', 'Примите предложение или откажитесь от него до указанного срока', ['ACCEPT_OFFER', 'REJECT_OFFER', 'WITHDRAW']],
  ['DECLINED', 4, 'failed', 'Банк не может одобрить заявку', 'Посмотрите причину и что можно сделать', ['NEW_APPLICATION']],
  ['SIGNING', 5, 'action_required', 'Готовим договор к подписанию', 'Подпишите договор кодом подтверждения', ['SIGN', 'WITHDRAW']],
  ['DISBURSED', 6, 'done', 'Деньги зачислены на счёт', null, ['NEW_APPLICATION']],
  ['WITHDRAWN', 3, 'cancelled', 'Заявка отозвана', 'Можно подать новую заявку', ['NEW_APPLICATION']],
];
const stageNames = ['Заявка', 'Проверка данных', 'Оценка', 'Решение', 'Подписание', 'Выдача'];
// Dedicated detail scenarios leave the existing demo lists unchanged.
export const applicationScenarios: Schema['ApplicationClient'][] = scenarioStages.map(([state, index, status, what_happens, what_to_do, allowed_actions], position) => {
  const base = applications[0]!;
  return {
    ...base, id: `30000000-0000-4000-8000-${String(101 + position).padStart(12, '0')}`, number: 1101 + position, state,
    stage: { index, code: base.timeline[index - 1]!.stage_code, title: stageNames[index - 1]!, what_happens, what_to_do },
    timeline: base.timeline.map((step, i) => ({ ...step, title: stageNames[i]!, status: i < index - 1 ? 'done' : i === index - 1 ? status : 'pending', at: i < index ? `2026-10-23T09:0${i}:00Z` : null })),
    offer: ['OFFER_ISSUED', 'SIGNING', 'DISBURSED'].includes(state) ? base.offer : null,
    client_reason: state === 'DECLINED' ? { code: 'HIGH_LOAD', category: 'Долговая нагрузка', text: 'Текущая долговая нагрузка слишком высока', action: 'Рассмотрите овердрафт или подайте заявку позже', retry_after: null } : null,
    info_request: state === 'INFO_REQUESTED' ? { id: '50000000-0000-4000-8000-000000000001', due_at: '2026-10-28T09:00:00Z', items: [{ item_code: 'REVENUE_CONFIRM', question: 'Подтвердите выручку за год', requires_value: true }] } : null,
    allowed_actions,
  };
});
applicationScenarios.push({
  ...applications[1]!, id: '30000000-0000-4000-8000-000000000109', number: 1109,
  stage: { ...applications[1]!.stage, what_happens: 'Предложение готово', what_to_do: 'Ждём решения подписанта компании' },
  timeline: applications[1]!.timeline.map((step, index) => ({ ...step, title: stageNames[index]!, status: index === 3 ? 'current' : step.status })),
  allowed_actions: [],
});

// Visual-only detail route; the public demo lists and existing personas stay stable.
const visualInfo = applicationScenarios.find((item) => item.state === 'INFO_REQUESTED')!;
applicationScenarios.push({
  ...visualInfo, id: '30000000-0000-4000-8000-000000001042', number: 1042,
  timeline: visualInfo.timeline.map((step, index) => ({ ...step, at: index < 2 ? '2026-10-23T11:02:00Z' : null })),
  info_request: { ...visualInfo.info_request!, due_at: '2026-10-30T20:59:59Z' },
});

// Catalog: docs/TASKS.md F-01 and the product showcase in contracts/codes.md.
export const products: Schema['Product'][] = [
  { code: 'EXPRESS', name: 'Экспресс-кредит', description: 'На любые цели бизнеса', purposes: ['WORKING_CAPITAL', 'CASH_GAP', 'EQUIPMENT', 'OTHER'], min_amount: 300000, max_amount: 5000000, min_term_months: 6, max_term_months: 36, rate_from: 22.00, requires_guarantor_ooo: true, key_rate: 14.00, key_rate_date: '2026-10-23' },
  { code: 'WORKING_CAPITAL', name: 'Оборотный кредит', description: 'На пополнение оборотных средств', purposes: ['WORKING_CAPITAL', 'CASH_GAP'], min_amount: 500000, max_amount: 15000000, min_term_months: 3, max_term_months: 24, rate_from: 21.00, requires_guarantor_ooo: true, key_rate: 14.00, key_rate_date: '2026-10-23' },
  { code: 'OVERDRAFT', name: 'Овердрафт', description: 'На покрытие кассовых разрывов', purposes: ['CASH_GAP', 'WORKING_CAPITAL'], min_amount: 100000, max_amount: 5000000, min_term_months: 12, max_term_months: 12, rate_from: 24.00, requires_guarantor_ooo: true, key_rate: 14.00, key_rate_date: '2026-10-23' },
];
