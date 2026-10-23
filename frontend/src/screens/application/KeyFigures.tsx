import { Button } from '@mantine/core';
import type { components } from '../../api/schema';
import { formatMoney } from '../../ui/status';
import type { Application } from './presentation';
import css from './Card.module.css';

export default function KeyFigures({ application, calculation, error, onRetry }: { application: Application; calculation?: components['schemas']['CalculatorResponse']; error: boolean; onRetry: () => void }) {
  const offer = application.offer;
  const rate = offer?.rate ?? calculation?.rate_estimate;
  const payment = offer ? offer.monthly_payment : calculation?.monthly_payment;
  const prefix = offer ? '' : 'около ';
  const figures = [
    ['Сумма', formatMoney(offer?.amount ?? application.amount)], ['Срок', `${offer?.term_months ?? application.term_months} мес.`],
    ['Ставка', rate === undefined ? 'Рассчитываем…' : `${prefix}${rate.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}\u00a0%`],
    [offer ? 'Платёж в месяц' : 'Платёж в месяц (оценка)', payment === null ? 'Проценты — только за использованные дни' : payment === undefined ? 'Рассчитываем…' : `${prefix}${formatMoney(payment)}`],
  ];
  return <section aria-label="Ключевые цифры">
    <div className={css.figures}>{figures.map(([label, value], index) => <div key={label} className={css.figure}><span className={css.muted}>{label}</span><span className={css.figureValue}>{error && !offer && index > 1 ? 'Расчёт недоступен' : value}</span></div>)}</div>
    {error && !offer && <><p role="alert" className={css.muted}>Не удалось рассчитать предварительные условия.</p><Button variant="default" size="xs" onClick={onRetry}>Повторить расчёт</Button></>}
  </section>;
}
