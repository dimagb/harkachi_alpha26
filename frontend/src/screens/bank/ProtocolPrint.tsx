import { Button, Loader } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router';
import { api } from '../../api/client';
import { formatMoney } from '../../ui/status';
import { factorMeta } from './factorMeta';
import { effectLabels, formatAt, formatPercent, outcomeLabels, productLabels, sourceLabels, type BankDecision } from './labels';
import { EventsTable } from './journal/EventsPanel';
import css from './ProtocolPrint.module.css';

const rate = (value: number) => `${new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)} %`;
function DecisionSection({ decision }: { decision: BankDecision }) {
  const policy = decision.policy;
  const recommendation = decision.recommendation;
  return <section className={css.decision} aria-label={`${decision.kind === 'AUTO' ? 'Автоматическое' : 'Ручное'} решение`}>
    <h2>{decision.kind === 'AUTO' ? 'Автоматическое решение' : `Специалист: ${decision.made_by ?? '—'}`}</h2>
    <p><strong>{outcomeLabels[decision.outcome]}</strong> · <time dateTime={decision.created_at}>{formatAt(decision.created_at)}</time> · Версия правил: {decision.config_version} · Ключевая ставка: {rate(decision.key_rate)}</p>
    {decision.kind === 'MANUAL' ? <p>Комментарий: {decision.comment ?? '—'}</p> : <>
      <h3>Факторы оценки</h3>
      <table aria-label="Факторы оценки"><thead><tr><th>Признак</th><th>Значение</th><th>Баллы / максимум</th><th>Правило</th></tr></thead><tbody>
        {decision.factors.map((factor, i) => <tr key={`${factor.code}-${i}`}><td>{factorMeta[factor.code]?.label ?? factor.title}</td><td>{factor.value}</td><td>{factor.points} / {factor.max_points}</td><td>{factor.rule}</td></tr>)}
        {!decision.factors.length && <tr><td colSpan={4}>Оценка по признакам не проводилась</td></tr>}
      </tbody></table>
      <p><strong>Итого {decision.score ?? '—'} / 100 · Класс {decision.grade ?? '—'}</strong></p>
      <h3>Сработавшие правила</h3>
      {decision.rules_fired.length ? <table aria-label="Сработавшие правила"><thead><tr><th>Правило</th><th>Значение</th><th>Порог</th><th>Эффект</th></tr></thead><tbody>{decision.rules_fired.map((rule, i) => <tr key={i}><td>{rule.title} ({rule.code})</td><td>{rule.value}</td><td>{rule.threshold}</td><td>{effectLabels[rule.effect]}</td></tr>)}</tbody></table> : <p>Нет</p>}
      <h3>Внутренние причины</h3>{decision.internal_reasons.length ? <ul>{decision.internal_reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul> : <p>Нет</p>}
      <h3>Расчёт условий</h3>
      {policy ? <><table aria-label="Расчёт условий"><tbody>{[
        ['Ставка', rate(policy.rate)], ['Средний оборот', formatMoney(policy.avg_turnover)], ['Текущие платежи', formatMoney(policy.existing_payments)],
        ['Свободный платёж', formatMoney(policy.free_payment)], ['Лимит по оборотам', formatMoney(policy.cap_by_turnover)], ['Максимальная сумма', formatMoney(policy.max_amount)],
        ['Запрошенный платёж', policy.requested_payment === null ? '—' : formatMoney(policy.requested_payment)], ['Платежи к обороту', policy.ptr_requested === null ? '—' : formatPercent(policy.ptr_requested * 100)],
      ].map(([label, value]) => <tr key={label}><th scope="row">{label}</th><td>{value}</td></tr>)}</tbody></table>{policy.steps.length ? <ol>{policy.steps.map((step, i) => <li key={i}>{step}</li>)}</ol> : <p>Дополнительных шагов расчёта нет</p>}</> : <p>Не рассчитывались</p>}
      <h3>Рекомендация системы</h3>
      {recommendation ? <p>{outcomeLabels[recommendation.outcome]}{recommendation.amount !== null ? ` · ${formatMoney(recommendation.amount)}` : ''}{recommendation.term_months !== null ? ` · ${recommendation.term_months} мес.` : ''}{recommendation.rate !== null ? ` · ${rate(recommendation.rate)}` : ''}</p> : <p>Нет рекомендации</p>}
      <h3>Что изменило бы решение</h3>{decision.what_if.length ? <ul>{decision.what_if.map((text, i) => <li key={i}>{text}</li>)}</ul> : <p>Дополнительных условий нет</p>}
    </>}
  </section>;
}
export default function ProtocolPrint() {
  const { id = '' } = useParams();
  const query = useQuery({ queryKey: ['bank', 'application', id], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/underwriting/applications/{id}', { params: { path: { id } }, signal });
    if (error || !data) throw new Error(error?.error.message ?? 'Не удалось загрузить протокол');
    return data;
  } });
  if (query.isPending) return <main className={css.page}><div role="status"><Loader size="sm" color="gray" /> Загружаем протокол…</div></main>;
  if (query.isError) return <main className={css.page}><div role="alert"><p>{query.error.message}</p><Button onClick={() => void query.refetch()}>Повторить</Button></div></main>;
  const app = query.data;
  return <main className={css.page}>
    <div className={css.toolbar}><span>Версия для печати · время по Москве</span><Button color="gray" onClick={() => window.print()}>Печать</Button></div>
    <header className={css.header}><h1>Протокол решения по заявке № {app.number}</h1><p><strong>{app.company.name}</strong> · ИНН {app.company.inn} · ОГРН {app.company.ogrn}</p><p>{productLabels[app.product_code]} · {formatMoney(app.amount)} · {app.term_months} мес.</p><p>Дата печати: {new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeStyle: 'short', timeZone: 'Europe/Moscow' }).format(new Date())}</p></header>
    {[...app.decisions].sort((a, b) => b.created_at.localeCompare(a.created_at)).map(decision => <DecisionSection key={decision.id} decision={decision} />)}
    {!app.decisions.length && <p>По заявке ещё нет решений</p>}
    <section><h2>Сведения источников</h2><table aria-label="Сведения источников"><thead><tr><th>Источник</th><th>Статус</th><th>Время получения (Москва)</th></tr></thead><tbody>{app.external_checks.map((check, i) => <tr key={i}><td>{sourceLabels[check.source]}</td><td>{check.status === 'OK' ? 'Получены' : check.status === 'FAILED' ? 'Источник не ответил' : 'Ожидание'}</td><td>{check.fetched_at ? formatAt(check.fetched_at) : '—'}</td></tr>)}</tbody></table></section>
    <section><h2>История заявки</h2><EventsTable events={app.events} /></section>
    <footer className={css.footer}>Заявка № {app.number} · Протокол решения</footer>
  </main>;
}
