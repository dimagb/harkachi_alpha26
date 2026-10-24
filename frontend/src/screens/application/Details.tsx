import type { components } from '../../api/schema';
import { purposeLabels } from '../../ui/labels';
import { formatMoney } from '../../ui/status';
import type { Application } from './presentation';
import css from './Card.module.css';

export default function Details({ application, company, sourceNote, showRequestedTerms = false }: { application: Application; company?: components['schemas']['MeResponse']['companies'][number]['company']; sourceNote?: string; showRequestedTerms?: boolean }) {
  return <section aria-label="Детали заявки"><dl className={css.details}>
    {showRequestedTerms && <><dt>Сумма заявки</dt><dd>{formatMoney(application.amount)}</dd><dt>Срок</dt><dd>{application.term_months} мес.</dd></>}
    <dt>Цель</dt><dd>{application.purpose === 'OTHER' ? application.purpose_text : purposeLabels[application.purpose]}</dd>
    <dt>Выручка за год</dt><dd>{formatMoney(application.declared_revenue_year)}</dd>
    <dt>Компания</dt><dd><span>{company?.name ?? 'Сведения о компании недоступны'}</span>{company && <span style={{ color: 'var(--cc-ink-2)' }}>ИНН {company.inn}</span>}{sourceNote && <span className={css.source}>{sourceNote}</span>}</dd>
  </dl></section>;
}
