import type { components } from '../api/schema';

export const purposeLabels = {
  WORKING_CAPITAL: 'Оборотные средства',
  CASH_GAP: 'Кассовый разрыв',
  EQUIPMENT: 'Оборудование и развитие',
  OTHER: 'Другое',
} satisfies Record<components['schemas']['ApplicationCreate']['purpose'], string>;

export const stateLabels = {
  DRAFT: 'Черновик', SUBMITTED: 'Заявка отправлена', VALIDATION: 'Проверяем заявку',
  ENRICHMENT: 'Собираем сведения', ASSESSMENT: 'Оцениваем заявку', MANUAL_REVIEW: 'Рассматривает специалист',
  INFO_REQUESTED: 'Нужны сведения', OFFER_ISSUED: 'Предложение готово', DECLINED: 'Отказ',
  SIGNING: 'Ожидает подписания', SIGNED: 'Подписано', DISBURSED: 'Деньги выданы',
  WITHDRAWN: 'Заявка отозвана', EXPIRED: 'Срок истёк',
} satisfies Record<components['schemas']['ApplicationListItem']['state'], string>;
