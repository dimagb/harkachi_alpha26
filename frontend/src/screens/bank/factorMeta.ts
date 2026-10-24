type Source = 'EGRUL' | 'BKI' | 'FNS' | 'BANK';
export type SourceField = { path: string; label: string; money?: boolean };
type FactorMeta = { label: string; source: Source; fields: SourceField[]; average?: boolean };
const turnover: SourceField[] = [{ path: 'turnover_12m', label: 'Поступления за 12 месяцев', money: true }];
export const factorMeta: Record<string, FactorMeta> = {
  business_age: { label: 'Срок бизнеса', source: 'EGRUL', fields: [{ path: 'reg_date', label: 'Дата регистрации' }] },
  industry_risk: { label: 'Отрасль', source: 'EGRUL', fields: [{ path: 'okved_main', label: 'Основной ОКВЭД' }] },
  mass_registration: { label: 'Массовый руководитель или адрес', source: 'FNS', fields: [{ path: 'mass_director', label: 'Массовый руководитель' }, { path: 'mass_address', label: 'Массовый адрес' }] },
  turnover_stability: { label: 'Стабильность поступлений', source: 'BANK', fields: turnover },
  turnover_trend: { label: 'Тренд поступлений', source: 'BANK', fields: turnover },
  zero_months: { label: 'Месяцы без поступлений', source: 'BANK', fields: turnover },
  payment_to_turnover: { label: 'Платежи к поступлениям', source: 'BKI', fields: [{ path: 'summary.monthly_payments_total', label: 'Платежи по кредитам в месяц', money: true }], average: true },
  debt_to_turnover: { label: 'Долг к годовому обороту', source: 'BKI', fields: [{ path: 'summary.total_balance', label: 'Остаток долга', money: true }], average: true },
  delinquency_12m: { label: 'Просрочки за 12 мес.', source: 'BKI', fields: [{ path: 'summary.max_dpd_12m', label: 'Максимальная просрочка за 12 мес., дней' }, { path: 'summary.current_overdue_total', label: 'Текущая просроченная задолженность', money: true }] },
  credit_history_length: { label: 'Длина кредитной истории', source: 'BKI', fields: [{ path: 'summary.credit_history_months', label: 'Длина кредитной истории, мес.' }] },
  bureau_inquiries_30d: { label: 'Запросы в БКИ за 30 дней', source: 'BKI', fields: [{ path: 'summary.inquiries_30d', label: 'Запросы в БКИ за 30 дней' }] },
  payment_discipline: { label: 'Налоги и взыскания', source: 'FNS', fields: [{ path: 'tax_debt', label: 'Налоговый долг', money: true }, { path: 'enforcement_sum', label: 'Исполнительные производства', money: true }, { path: 'arbitration_defendant_sum', label: 'Сумма арбитражных споров', money: true }] },
};
export const factorGroups = [
  { title: 'Бизнес', codes: ['business_age', 'industry_risk', 'mass_registration'] },
  { title: 'Обороты', codes: ['turnover_stability', 'turnover_trend', 'zero_months'] },
  { title: 'Нагрузка', codes: ['payment_to_turnover', 'debt_to_turnover'] },
  { title: 'Кредитная история', codes: ['delinquency_12m', 'credit_history_length', 'bureau_inquiries_30d'] },
  { title: 'Дисциплина', codes: ['payment_discipline'] },
];
export const responseLabels: Record<string, string> = {
  inn: 'ИНН', ogrn: 'ОГРН', kind: 'Тип', name: 'Название', status: 'Статус', reg_date: 'Дата регистрации', okved_main: 'Основной ОКВЭД', address: 'Юридический адрес', director: 'Руководитель', full_name: 'ФИО', founders: 'Учредители', share_pct: 'Доля, %', loans: 'Кредиты', type: 'Вид кредита', balance: 'Остаток долга', monthly_payment: 'Платёж в месяц', current_overdue: 'Текущая просрочка', max_dpd_12m: 'Максимальная просрочка за 12 мес., дней', summary: 'Сводка', monthly_payments_total: 'Платежи по кредитам в месяц', total_balance: 'Остаток долга', current_overdue_total: 'Текущая просроченная задолженность', credit_history_months: 'Длина кредитной истории, мес.', inquiries_30d: 'Запросы в БКИ за 30 дней', tax_debt: 'Налоговый долг', enforcement_sum: 'Исполнительные производства', arbitration_defendant_sum: 'Сумма арбитражных споров', bankruptcy: 'Банкротство', mass_director: 'Массовый руководитель', mass_address: 'Массовый адрес', msp_registry: 'Реестр МСП', included: 'Включён', category: 'Категория',
};
