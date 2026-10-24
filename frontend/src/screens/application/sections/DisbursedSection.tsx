import type { components } from '../../../api/schema';
import { formatMoney } from '../../../ui/status';
import card from '../Card.module.css';
import css from './SigningSection.module.css';
import { calculateSchedule } from './schedule';
const date = (value: string) => new Date(value).toLocaleDateString('ru-RU', { timeZone: 'Europe/Moscow' });
export default function DisbursedSection({ application }: { application: components['schemas']['ApplicationClient'] }) {
  if (application.state !== 'DISBURSED' || !application.offer) return null;
  const offer = application.offer;
  const issuedAt = application.timeline.find((step) => step.stage_code === 'DISBURSEMENT')?.at;
  const rows = issuedAt && offer.product_code !== 'OVERDRAFT' ? calculateSchedule(offer.amount, offer.rate, offer.term_months, issuedAt) : [];
  return <section id="disbursed" aria-label="Выдача" className={`${card.card} ${css.section}`}>
    <h3 className={card.title}>Деньги зачислены на счёт</h3><strong className={css.amount}>{formatMoney(offer.amount)}</strong>
    <dl className={card.details}><dt>Дата выдачи</dt><dd>{issuedAt ? date(issuedAt) : 'Уточняется'}</dd><dt>Ставка</dt><dd>{offer.rate.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %</dd><dt>Срок</dt><dd>{offer.term_months} мес.</dd><dt>Платёж в месяц</dt><dd>{offer.monthly_payment === null ? 'Проценты — только за использованные дни' : formatMoney(offer.monthly_payment)}</dd></dl>
    {offer.product_code === 'OVERDRAFT' ? <p>Лимит открыт: {formatMoney(offer.amount)}. Проценты — только за использованные дни</p> : rows.length > 0 && <div className={css.scroll} tabIndex={0} role="region" aria-label="Прокрутка графика платежей"><table className={css.table}><caption>График платежей (расчётный)</caption><thead><tr>{['№', 'Дата', 'Платёж', 'В т. ч. проценты', 'Основной долг', 'Остаток'].map((text) => <th scope="col" key={text}>{text}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.number}><td>{row.number}</td><td>{date(row.date)}</td><td>{formatMoney(row.payment)}</td><td>{formatMoney(row.interest)}</td><td>{formatMoney(row.principal)}</td><td>{formatMoney(row.balance)}</td></tr>)}</tbody></table></div>}
  </section>;
}
