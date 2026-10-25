import { Tabs } from '@mantine/core';
import { formatMoney } from '../../../ui/status';
import { purposeLabels } from '../../../ui/labels';
import { effectLabels, eventLabels, formatAt, formatPercent, internalReasonLabel, outcomeLabels, productLabels, stateLabels, type BankApplication, type BankDecision } from '../labels';
import css from './Underwriter.module.css';

function deadline(at: string) {
  return new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(at)).replace(',', '');
}

export function Parameters({ application }: { application: BankApplication }) {
  const offer = application.offer;
  const request = application.state === 'INFO_REQUESTED' ? application.info_request : null;
  return <section className={css.section} aria-label="Параметры заявки"><h2>Параметры заявки</h2>
    <dl className={css.sourceDetails} style={{ margin: 0 }}>
      <dt>Продукт</dt><dd>{productLabels[application.product_code]}</dd>
      <dt>Сумма</dt><dd>{formatMoney(application.amount)}</dd>
      <dt>Срок</dt><dd>{application.term_months} мес.</dd>
      <dt>Цель</dt><dd>{application.purpose_text || purposeLabels[application.purpose]}</dd>
      <dt>Заявленная выручка за год</dt><dd>{formatMoney(application.declared_revenue_year)}</dd>
    </dl>
    {offer && <><h3>Условия предложения</h3><dl className={css.sourceDetails} style={{ margin: 0 }}>
      <dt>Продукт</dt><dd>{productLabels[offer.product_code]}</dd>
      <dt>Сумма</dt><dd>{formatMoney(offer.amount)}</dd>
      <dt>Срок</dt><dd>{offer.term_months} мес.</dd>
      <dt>Ставка</dt><dd>{offer.rate.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %</dd>
      <dt>Платёж в месяц</dt><dd>{offer.monthly_payment === null ? 'Проценты — только за использованные дни' : formatMoney(offer.monthly_payment)}</dd>
    </dl><p>Действует до {deadline(offer.expires_at)} (Москва)</p></>}
    {request && <><h3>Запрошенные данные</h3><ul>{request.items.map((item, index) => <li key={`${item.item_code}-${index}`}>{item.question}</li>)}</ul><p>Ответить до {deadline(request.due_at)} (Москва)</p></>}
  </section>;
}

export function Rules({ decision }: { decision: BankDecision }) {
  const reasons = [...new Set(decision.internal_reasons)].filter(code => !decision.rules_fired.some(rule => rule.code === code));
  return (!!decision.rules_fired.length || !!reasons.length) && <section className={css.section} aria-label="Сработавшие правила"><h2>Сработавшие правила</h2>{decision.rules_fired.map((rule, index) => <div key={`${rule.code}-${index}`} className={css.rule}><div className={css.ruleCopy}><strong title={rule.code}>{rule.title}</strong><span>Факт: {rule.value}</span><span>Порог: {rule.threshold}</span></div><span className={css.badge} data-tone={rule.effect === 'STOP' ? 'stop' : rule.effect === 'ROUTE' ? 'wait' : 'gray'}>{effectLabels[rule.effect]}</span></div>)}{!!reasons.length && <ul>{reasons.map(code => <li key={code} title={code}>{internalReasonLabel(code)}</li>)}</ul>}</section>;
}

export function Turnover({ application }: { application: BankApplication }) {
  const values = application.turnover_12m;
  const average = values.length ? values.reduce((sum, m) => sum + m.amount, 0) / values.length : 0;
  const top = Math.max(1, ...values.map(m => m.amount)) * 1.2;
  return <section className={css.section} aria-label="Поступления на счёт за 12 месяцев"><h2>Поступления на счёт за 12 месяцев</h2><div className={css.chartLegend}><span>тыс. ₽</span><span>Последние 3 месяца</span><span>Среднее {formatMoney(Math.round(average))}</span></div><div className={css.chartScroll} tabIndex={0} aria-label="График поступлений"><div className={css.chart} role="img" aria-label="Поступления за 12 месяцев, значения в тысячах рублей"><span className={css.averageLine} style={{ bottom: `${average / top * 160}px` }} />{values.map((m, i) => <div key={m.month} className={css.chartColumn}><span>{new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(m.amount / 1000)}</span><span className={css.chartBar} style={{ height: `${m.amount / top * 160}px`, background: i >= values.length - 3 ? 'var(--mantine-color-wait-4)' : 'var(--mantine-color-gray-4)' }} /><span className={css.month}>{new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', month: 'short' }).format(new Date(`${m.month}-01T00:00:00Z`)).replace('.', '')}</span></div>)}</div></div></section>;
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
