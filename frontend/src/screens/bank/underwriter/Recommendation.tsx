import { formatMoney } from '../../../ui/status';
import { formatPercent, monthlyPayment, type BankDecision } from '../labels';
import css from './Underwriter.module.css';

export default function Recommendation({ decision }: { decision: BankDecision }) {
  const recommendation = decision.recommendation;
  const financed = recommendation?.outcome !== 'DECLINE' && recommendation?.amount != null && recommendation.term_months != null && recommendation.rate != null;
  return <>
    <section className={css.recommendation} data-tone={recommendation?.outcome === 'DECLINE' ? 'stop' : recommendation?.outcome === 'COUNTER' ? 'wait' : 'ok'} aria-label="Рекомендация системы">
      <span className={css.recommendationLabel}>Рекомендация системы</span>
      <div className={css.recommendationText}>{!recommendation ? 'Рекомендация пока не сформирована' : recommendation.outcome === 'DECLINE' ? 'Отказать' : `${recommendation.outcome === 'APPROVE' ? 'Одобрить' : 'Предложить'} ${recommendation.amount === null ? '—' : formatMoney(recommendation.amount)} на ${recommendation.term_months ?? '—'} мес. под ${recommendation.rate === null ? '—' : formatPercent(recommendation.rate)}`}</div>
      {financed && <div className={css.payment}><span className={css.muted}>Платёж в месяц</span><strong>{formatMoney(monthlyPayment(recommendation.amount!, recommendation.rate!, recommendation.term_months!))}</strong></div>}
    </section>
    {!!decision.what_if.length && <section className={css.whatIf} aria-label="Что изменило бы решение"><span className={css.caption}>Что изменило бы решение</span><ul>{decision.what_if.map((text, i) => <li key={i}>{text}</li>)}</ul></section>}
  </>;
}
