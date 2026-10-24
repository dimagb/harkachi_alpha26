import { Tabs } from '@mantine/core';
import { formatMoney } from '../../../ui/status';
import { effectLabels, eventLabels, formatAt, formatPercent, outcomeLabels, stateLabels, type BankApplication, type BankDecision } from '../labels';
import css from './Underwriter.module.css';

export function Rules({ decision }: { decision: BankDecision }) {
  return !!decision.rules_fired.length && <section className={css.section} aria-label="Сработавшие правила"><h2>Сработавшие правила</h2>{decision.rules_fired.map((rule, index) => <div key={`${rule.code}-${index}`} className={css.rule}><div className={css.ruleCopy}><strong title={rule.code}>{rule.title}</strong><span>Факт: {rule.value}</span><span>Порог: {rule.threshold}</span></div><span className={css.badge} data-tone={rule.effect === 'STOP' ? 'stop' : rule.effect === 'ROUTE' ? 'wait' : 'gray'}>{effectLabels[rule.effect]}</span><code className={css.ruleCode}>{rule.code}</code></div>)}{!!decision.internal_reasons.length && <ul>{decision.internal_reasons.map((text, i) => <li key={i}>{text}</li>)}</ul>}</section>;
}

export function Turnover({ application }: { application: BankApplication }) {
  const values = application.turnover_12m;
  const average = values.length ? values.reduce((sum, m) => sum + m.amount, 0) / values.length : 0;
  const top = Math.max(1, ...values.map(m => m.amount)) * 1.2;
  return <section className={css.section} aria-label="Поступления на счёт за 12 месяцев"><h2>Поступления на счёт за 12 месяцев</h2><div className={css.chartLegend}><span>тыс. ₽</span><span>Последние 3 месяца</span><span>Среднее {formatMoney(Math.round(average))}</span></div><div className={css.chartScroll}><div className={css.chart} role="img" aria-label="Поступления за 12 месяцев, значения в тысячах рублей"><span className={css.averageLine} style={{ bottom: `${average / top * 160}px` }} />{values.map((m, i) => <div key={m.month} className={css.chartColumn}><span>{new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(m.amount / 1000)}</span><span className={css.chartBar} style={{ height: `${m.amount / top * 160}px`, background: i >= values.length - 3 ? 'var(--mantine-color-wait-4)' : 'var(--mantine-color-gray-4)' }} /><span className={css.month}>{new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', month: 'short' }).format(new Date(`${m.month}-01T00:00:00Z`)).replace('.', '')}</span></div>)}</div></div></section>;
}

export function Policy({ decision }: { decision: BankDecision }) {
  const policy = decision.policy;
  if (!policy) return null;
  const tiles = [['Средний оборот', formatMoney(policy.avg_turnover)], ['Текущие платежи', formatMoney(policy.existing_payments)], ['Свободно для платежа', formatMoney(policy.free_payment)], ['Лимит по оборотам', formatMoney(policy.cap_by_turnover)], ['Ставка', formatPercent(policy.rate)]];
  return <section className={css.section} aria-label="Расчёт условий"><h2>Расчёт условий</h2><div className={css.policyTiles}>{tiles.map(([label, value]) => <div key={label}><span className={css.caption}>{label}</span><strong>{value}</strong></div>)}</div>{!!policy.steps.length && <ol>{policy.steps.map((step, i) => <li key={i}>{step}</li>)}</ol>}</section>;
}

export function Protocol({ application }: { application: BankApplication }) {
  return <Tabs defaultValue="protocol" className={css.protocol} keepMounted={false} color="gray"><Tabs.List><Tabs.Tab value="protocol">Протокол решения</Tabs.Tab><Tabs.Tab value="history">История заявки</Tabs.Tab></Tabs.List>
    <Tabs.Panel value="protocol"><ol className={css.log}>{[...application.decisions].sort((a, b) => b.created_at.localeCompare(a.created_at)).map(decision => <li key={decision.id}><time dateTime={decision.created_at}>{formatAt(decision.created_at)}</time><span>{decision.kind === 'AUTO' ? 'Авто' : 'Специалист'} · {decision.made_by ?? 'Система'}</span><div><strong>{outcomeLabels[decision.outcome]}</strong><p>{decision.comment}</p><span className={css.muted}>правила v{decision.config_version}</span></div></li>)}</ol></Tabs.Panel>
    <Tabs.Panel value="history"><ol className={css.log}>{application.events.map((event, i) => <li key={i}><time dateTime={event.at}>{formatAt(event.at)}</time><span>{event.actor}</span><div><strong>{event.event_type === 'DECISION_MADE' && event.actor === 'Система' ? 'Решение принято системой' : eventLabels[event.event_type] ?? event.event_type}</strong>{(event.from_state || event.to_state) && <p>{event.from_state ? stateLabels[event.from_state] : '—'} → {event.to_state ? stateLabels[event.to_state] : '—'}</p>}{event.note && <p>{event.note}</p>}</div></li>)}</ol></Tabs.Panel>
  </Tabs>;
}
