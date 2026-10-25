import type { components } from '../../api/schema';

export type BankApplication = components['schemas']['ApplicationBank'];
export type BankDecision = components['schemas']['DecisionBank'];
export type DecisionRequest = components['schemas']['UnderwriterDecisionRequest'];
export const routeLabels = {
  GRADE_C: 'Пограничная оценка', AMOUNT_ABOVE_AUTO: 'Сумма выше порога автоматического решения',
  NO_AUTO_CONSENT: 'Нет согласия на автоматическое решение', SOURCE_UNAVAILABLE: 'Источник данных недоступен',
  OBJECTION: 'Клиент не согласен с решением', INFO_RESPONSE: 'Клиент ответил на вопросы',
} satisfies Record<NonNullable<BankDecision['route_reason']>, string>;
export const outcomeLabels = { APPROVE: 'Одобрить', COUNTER: 'Встречное', DECLINE: 'Отказать', REQUEST_INFO: 'Запросить данные', RETRY_ENRICHMENT: 'Повторить сбор сведений', MANUAL: 'К специалисту' } satisfies Record<BankDecision['outcome'], string>;
export const productLabels = { EXPRESS: 'Экспресс-кредит', WORKING_CAPITAL: 'Оборотный кредит', OVERDRAFT: 'Овердрафт' };
export const effectLabels = { STOP: 'Стоп-фактор', ROUTE: 'К специалисту', INFO: 'Запрос данных', POLICY: 'Политика' };
export const internalReasonLabels: Record<string, string> = {
  ...routeLabels,
  SF_INACTIVE: 'Компания не действует',
  SF_BANKRUPTCY: 'Процедура банкротства',
  SF_AGE: 'Недостаточный срок бизнеса',
  SF_OVERDUE: 'Просроченная задолженность',
  SF_TAX_DEBT: 'Налоги и обязательства',
  SF_OKVED: 'Вид деятельности не подходит',
  SF_ADDITIONAL: 'Дополнительные проверки',
  ADDITIONAL_CHECKS: 'Дополнительные проверки',
  LOW_SCORE: 'Недостаточная оценка финансовых показателей',
  HIGH_LOAD: 'Высокая долговая нагрузка',
  UNDERWRITER_DECLINE: 'Отказ специалиста банка',
  CLIENT_REJECTED_OFFER: 'Клиент отказался от предложения',
  CLIENT_WITHDREW: 'Клиент отозвал заявку',
  EXPIRED_INFO: 'Срок ответа на запрос истёк',
  EXPIRED_OFFER: 'Срок действия предложения истёк',
  VAL_REVENUE_MISMATCH: 'Нужно подтвердить выручку',
  VAL_PURPOSE_UNCLEAR: 'Нужно описать цель',
};
export function internalReasonLabel(code: string) {
  return internalReasonLabels[code] ?? (/^[A-Z][A-Z0-9_]+$/.test(code) ? 'Внутренняя причина решения' : code);
}
export const sourceLabels = { EGRUL: 'ЕГРЮЛ/ЕГРИП', BKI: 'БКИ', FNS: 'ФНС', BANK: 'Обороты по счёту в банке' };
export const eventLabels: Record<string, string> = {
  STATE_CHANGED: 'Состояние изменено', SIGNATURE_REQUESTED: 'Запрошена подпись', CONSENT_SIGNED: 'Согласия подписаны',
  CHECK_REQUESTED: 'Сведения запрошены', CHECK_RECEIVED: 'Сведения получены', CHECK_FAILED: 'Источник не ответил',
  DECISION_MADE: 'Решение принято', OFFER_ISSUED: 'Предложение выдано', OFFER_ACCEPTED: 'Предложение принято',
  SIGNED: 'Договор подписан', DISBURSED: 'Деньги зачислены', BKI_REPORT: 'Отчёт в БКИ', OBJECTION_FILED: 'Возражение клиента', UNDERWRITER_OVERRIDE: 'Расхождение с рекомендацией',
};
export const stateLabels: Record<BankApplication['state'], string> = {
  DRAFT: 'Черновик', SUBMITTED: 'Подана', VALIDATION: 'Проверка заявки', INFO_REQUESTED: 'Запрошены данные', ENRICHMENT: 'Сбор сведений', ASSESSMENT: 'Оценка', MANUAL_REVIEW: 'Рассмотрение специалистом', OFFER_ISSUED: 'Предложение выдано', DECLINED: 'Отказ', SIGNING: 'Подписание', SIGNED: 'Подписана', DISBURSED: 'Выдана', WITHDRAWN: 'Отозвана', EXPIRED: 'Срок истёк',
};
export const reasonCategories: NonNullable<DecisionRequest['client_reason_category']>[] = ['Данные о компании', 'Финансовое положение', 'Срок ведения бизнеса', 'Кредитная история', 'Налоги и обязательства', 'Условия продукта', 'Дополнительные проверки', 'Финансовые показатели', 'Долговая нагрузка'];

export function formatAt(at: string) {
  const parts = new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(at));
  const value = (name: string) => parts.find(p => p.type === name)?.value ?? '';
  return `${value('day')}.${value('month')} ${value('hour')}:${value('minute')}`;
}
export function formatPercent(value: number) { return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value) + '\u00a0%'; }
export function waitingTime(since: string, now = Date.now()) {
  const minutes = Math.max(0, Math.floor((now - new Date(since).getTime()) / 60000));
  const hours = Math.floor(minutes / 60);
  if (hours >= 24) return `${Math.floor(hours / 24)} д${hours % 24 ? ` ${hours % 24} ч` : ''}`;
  if (hours) return `${hours} ч${minutes % 60 ? ` ${minutes % 60} мин` : ''}`;
  return `${minutes} мин`;
}
export function monthlyPayment(amount: number, rate: number, term: number) {
  const r = rate / 1200;
  return r === 0 ? Math.round(amount / term) : Math.round(amount * r / (1 - (1 + r) ** -term));
}
