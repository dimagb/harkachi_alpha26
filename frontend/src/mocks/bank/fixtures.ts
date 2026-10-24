import type { components } from '../../api/schema';

type Schema = components['schemas'];
const at = '2026-10-23T11:03:00Z';

// Копия contracts/personas.json: ooo_border.demo.expected.recommendation.
// Не импортируем contracts в браузер: Docker собирает только frontend/.
const scoring: [string, string, string, number, number, string][] = [
  ['business_age', 'Срок бизнеса', '14 мес.', 5, 10, 'От 12 до 23 месяцев: 5 из 10'],
  ['industry_risk', 'Отрасль', 'Электромонтаж, средний риск', 3, 5, 'Средний отраслевой риск: 3 из 5'],
  ['mass_registration', 'Массовый руководитель или адрес', 'Нет', 5, 5, 'Нет массовых признаков: 5 из 5'],
  ['turnover_stability', 'Стабильность поступлений', 'Коэффициент вариации 0,53', 5, 10, 'Умеренная изменчивость поступлений: 5 из 10'],
  ['turnover_trend', 'Тренд поступлений', 'Последние 3 мес. ниже на 13 %', 5, 10, 'Умеренное снижение: 5 из 10'],
  ['zero_months', 'Месяцы без поступлений', '0', 10, 10, 'Поступления каждый месяц: 10 из 10'],
  ['payment_to_turnover', 'Платежи к поступлениям', '22,3 %', 4, 15, 'Платежи с новым кредитом / средний оборот: 22,3 %, 4 из 15'],
  ['debt_to_turnover', 'Долг к годовому обороту', '64 %', 0, 10, 'Долг / годовой оборот: 64 %, 0 из 10'],
  ['delinquency_12m', 'Просрочки за 12 мес.', 'Нет', 10, 10, 'Просрочек нет: 10 из 10'],
  ['credit_history_length', 'Длина кредитной истории', '14 мес.', 3, 5, 'От 12 до 23 месяцев: 3 из 5'],
  ['bureau_inquiries_30d', 'Запросы в БКИ за 30 дней', '2', 2, 5, 'Два запроса за 30 дней: 2 из 5'],
  ['payment_discipline', 'Налоги и взыскания', 'Налоговый долг 20 000 ₽', 2, 5, 'Небольшой налоговый долг: 2 из 5'],
];
export const borderDecision: Schema['DecisionBank'] = {
  id: 'auto-border', kind: 'AUTO', outcome: 'MANUAL', client_reason_code: null,
  route_reason: 'GRADE_C', grade: 'C', score: 54,
  factors: scoring.map(([code, title, value, points, max_points, rule]) => ({ code, title, value, points, max_points, rule })),
  rules_fired: [], internal_reasons: ['Пограничная оценка: требуется решение специалиста.'],
  policy: { rate: 26, avg_turnover: 912500, existing_payments: 150000, free_payment: 123750, cap_by_turnover: 1825000, max_amount: 1825000, requested_payment: 53875, ptr_requested: 0.2234, steps: [] },
  recommendation: { outcome: 'APPROVE', amount: 1000000, term_months: 24, rate: 26 },
  what_if: ['Оценка B — при долге к годовому обороту до 50 % и без налогового долга.'],
  config_version: '1', key_rate: 14, made_by: null, comment: null, created_at: at,
};

// Реестровые поля, БКИ, ФНС и обороты: contracts/personas.json → ooo_border.
const border: Schema['ApplicationBank'] = {
  id: 'ooo_border', number: 1047, version: 1, company_id: 'company-border', state: 'MANUAL_REVIEW',
  product_code: 'EXPRESS', amount: 1000000, term_months: 24, purpose: 'WORKING_CAPITAL', purpose_text: null, declared_revenue_year: 12000000,
  stage: { index: 4, code: 'DECISION', title: 'Решение', what_happens: 'Заявку рассматривает специалист', what_to_do: 'Дождитесь решения' },
  timeline: [
    { stage_code: 'APPLICATION', title: 'Заявка', status: 'done', at: '2026-10-23T11:02:00Z' },
    { stage_code: 'CHECK', title: 'Проверка данных', status: 'done', at },
    { stage_code: 'ASSESSMENT', title: 'Оценка', status: 'done', at },
    { stage_code: 'DECISION', title: 'Решение', status: 'current', at: null },
    { stage_code: 'SIGNING', title: 'Подписание', status: 'pending', at: null },
    { stage_code: 'DISBURSEMENT', title: 'Выдача', status: 'pending', at: null },
  ],
  offer: null, client_reason: null, info_request: null, parties: [], allowed_actions: ['WITHDRAW'], awaiting_signature: false, objection: null,
  created_at: '2026-10-23T11:02:00Z', updated_at: at,
  company: { id: 'company-border', inn: '7705123452', ogrn: '1257700034567', kind: 'OOO', name: 'ООО «ТехноМонтаж»', status: 'ACTIVE', reg_date: '2025-08-01', okved_main: '43.21', address: 'г. Москва, Электродный пр., д. 9', director_full_name: 'Захаров Роман Олегович', founders: [{ full_name: 'Захаров Роман Олегович', share_pct: 100 }], avg_monthly_turnover: 912500, source_note: 'Данные из ЕГРЮЛ на 23.10.2026' },
  risk_flags: { aml_flag: false, fraud_flag: false },
  turnover_12m: [500000, 1500000, 500000, 1500000, 500000, 1500000, 500000, 1500000, 500000, 1050000, 350000, 1050000].map((amount, index) => ({ month: index < 2 ? `2025-${11 + index}` : `2026-${String(index - 1).padStart(2, '0')}`, amount })),
  decisions: [borderDecision],
  external_checks: [
    { source: 'EGRUL', status: 'OK', attempts: 1, fetched_at: at, response: { inn: '7705123452', ogrn: '1257700034567', kind: 'OOO', name: 'ООО «ТехноМонтаж»', status: 'ACTIVE', reg_date: '2025-08-01', okved_main: '43.21', address: 'г. Москва, Электродный пр., д. 9', director: { full_name: 'Захаров Роман Олегович' }, founders: [{ full_name: 'Захаров Роман Олегович', share_pct: 100 }] } },
    { source: 'BKI', status: 'OK', attempts: 1, fetched_at: at, response: { inn: '7705123452', kind: 'FULL', loans: [{ type: 'CREDIT', balance: 7000000, monthly_payment: 150000, current_overdue: 0, max_dpd_12m: 0 }], summary: { monthly_payments_total: 150000, total_balance: 7000000, current_overdue_total: 0, max_dpd_12m: 0, credit_history_months: 14, inquiries_30d: 2 } } },
    { source: 'FNS', status: 'OK', attempts: 1, fetched_at: at, response: { inn: '7705123452', tax_debt: 20000, enforcement_sum: 0, arbitration_defendant_sum: 0, bankruptcy: false, mass_director: false, mass_address: false, msp_registry: { included: true, category: 'MICRO' } } },
  ],
  events: [
    { at: '2026-10-23T11:02:00Z', event_type: 'STATE_CHANGED', from_state: 'DRAFT', to_state: 'SUBMITTED', actor: 'Захаров Роман Олегович', reason_code: null, note: 'Заявка подана' },
    { at, event_type: 'CHECK_RECEIVED', from_state: null, to_state: null, actor: 'Система', reason_code: null, note: 'Получены сведения ЕГРЮЛ, БКИ и ФНС' },
    { at, event_type: 'DECISION_MADE', from_state: 'ASSESSMENT', to_state: 'MANUAL_REVIEW', actor: 'Система', reason_code: null, note: 'Оценка 54 из 100, класс C' },
  ],
};

const failed: Schema['ApplicationBank'] = {
  ...structuredClone(border), id: 'source_unavailable', number: 1048,
  company: { ...border.company, id: 'company-source', name: 'ООО «Ритм»' }, company_id: 'company-source', updated_at: '2026-10-23T11:04:00Z',
  decisions: [{ ...borderDecision, id: 'auto-source', route_reason: 'SOURCE_UNAVAILABLE', factors: [], grade: null, score: null, policy: null, recommendation: null, what_if: [], internal_reasons: ['БКИ не ответил после трёх попыток.'] }],
  external_checks: border.external_checks.map(check => check.source === 'BKI' ? { ...check, status: 'FAILED', attempts: 3, fetched_at: null, response: null } : check),
};

// contracts/personas.json → ooo_aml: отказ до скоринга, SF_ADDITIONAL только банку.
const aml: Schema['ApplicationBank'] = {
  ...structuredClone(border), id: 'ooo_aml', number: 1046, state: 'DECLINED', term_months: 12, declared_revenue_year: 36000000,
  company_id: 'company-aml', company: { ...border.company, id: 'company-aml', inn: '7706123455', ogrn: '1227700045678', name: 'ООО «Альфа-Трейд»', reg_date: '2022-01-01', okved_main: '46.90', address: 'г. Москва, ул. Оптовая, д. 21', director_full_name: 'Сорокин Виктор Андреевич', founders: [{ full_name: 'Сорокин Виктор Андреевич', share_pct: 100 }], avg_monthly_turnover: 3000000 },
  risk_flags: { aml_flag: true, fraud_flag: false },
  turnover_12m: border.turnover_12m.map((m, i) => ({ ...m, amount: i % 2 ? 3600000 : 2400000 })),
  stage: { ...border.stage, what_happens: 'По заявке принято решение', what_to_do: null },
  timeline: border.timeline.map(step => step.stage_code === 'DECISION' ? { ...step, status: 'failed', at } : step),
  allowed_actions: ['NEW_APPLICATION'], client_reason: { code: 'ADDITIONAL_CHECKS', category: 'Дополнительные проверки', text: 'Заявка не одобрена по результатам дополнительных проверок', action: null, retry_after: null },
  decisions: [{ ...borderDecision, id: 'auto-aml', outcome: 'DECLINE', route_reason: null, grade: null, score: null, factors: [], policy: null, recommendation: { outcome: 'DECLINE', amount: null, term_months: null, rate: null }, what_if: [], client_reason_code: 'ADDITIONAL_CHECKS', rules_fired: [{ code: 'SF_ADDITIONAL', title: 'Дополнительные проверки', value: 'Признаки AML', threshold: 'Флаг установлен', effect: 'STOP' }], internal_reasons: ['Синтетический флаг ПОД/ФТ для теста'] }],
  external_checks: border.external_checks.map(check => ({ ...check, response: check.source === 'EGRUL' ? { inn: '7706123455', ogrn: '1227700045678', kind: 'OOO', name: 'ООО «Альфа-Трейд»', status: 'ACTIVE', reg_date: '2022-01-01', okved_main: '46.90', address: 'г. Москва, ул. Оптовая, д. 21', director: { full_name: 'Сорокин Виктор Андреевич' }, founders: [{ full_name: 'Сорокин Виктор Андреевич', share_pct: 100 }] } : check.source === 'BKI' ? { inn: '7706123455', kind: 'FULL', loans: [], summary: { monthly_payments_total: 0, total_balance: 0, current_overdue_total: 0, max_dpd_12m: 0, credit_history_months: 36, inquiries_30d: 0 } } : { ...check.response, inn: '7706123455', tax_debt: 0 } })),
  events: [{ at, event_type: 'DECISION_MADE', from_state: 'ASSESSMENT', to_state: 'DECLINED', actor: 'Система', reason_code: 'SF_ADDITIONAL', note: 'Отказ по дополнительным проверкам' }],
};

export const bankApplications: Schema['ApplicationBank'][] = [border, failed,
  ...(['AMOUNT_ABOVE_AUTO', 'NO_AUTO_CONSENT', 'OBJECTION', 'INFO_RESPONSE'] as const).map((route_reason, i): Schema['ApplicationBank'] => ({
    ...structuredClone(border), id: `background-${i}`, number: 1049 + i,
    company: { ...border.company, name: ['ООО «Север»', 'ИП Иванов', 'ИП Климова', 'ООО «Вектор»'][i]!, kind: i === 1 || i === 2 ? 'IP' : 'OOO' },
    updated_at: `2026-10-23T11:0${5 + i}:00Z`,
    decisions: [{ ...borderDecision, route_reason, grade: i === 0 ? 'B' : i === 2 ? 'D' : 'C' }],
  })), aml];
