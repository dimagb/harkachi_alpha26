import { Collapse } from '@mantine/core';
import { useId, useState } from 'react';
import type { components } from '../../../api/schema';
import { formatMoney } from '../../../ui/status';
import { factorGroups, factorMeta } from '../factorMeta';
import { formatAt, sourceLabels, type BankApplication, type BankDecision } from '../labels';
import { displayValue, fieldValue } from './Sources';
import css from './Underwriter.module.css';

function Bar({ points, max, total = false }: { points: number; max: number; total?: boolean }) {
  return <span className={css.bar} aria-hidden="true"><span style={{ width: `${Math.min(100, Math.max(0, max ? points / max * 100 : 0))}%`, background: total ? 'var(--cc-ink)' : points === max ? 'var(--cc-ok)' : points === 0 ? 'var(--cc-stop)' : 'var(--mantine-color-wait-4)' }} /></span>;
}
function Factor({ factor, application, decision }: { factor: components['schemas']['FactorLine']; application: BankApplication; decision: BankDecision }) {
  const [opened, setOpened] = useState(false);
  const id = useId();
  const meta = factorMeta[factor.code];
  const label = meta?.label ?? factor.title;
  const check = application.external_checks.find(check => check.source === meta?.source);
  // TODO(lead): turnover_12m не содержит fetched_at; нужен ли timestamp в следующей версии API?
  return <div>
    <button className={css.factorRow} aria-expanded={opened} aria-controls={id} onClick={() => setOpened(v => !v)}>
      <span className={css.factorName}><span className={css.sourceIcon} data-tone={factor.points === factor.max_points ? 'ok' : factor.points === 0 ? 'stop' : 'wait'} aria-hidden="true">{factor.points < factor.max_points ? '!' : '✓'}</span>{label}</span><span className={css.factorValue}>{factor.value}</span><Bar points={factor.points} max={factor.max_points} /><span className={css.points}>{factor.points}<span> / {factor.max_points}</span></span>
    </button>
    <Collapse expanded={opened} transitionDuration={120}>{opened && <div id={id} role="region" aria-label={`Первоисточник: ${label}`} className={css.primarySource}>
      <strong>{meta ? sourceLabels[meta.source] : 'Источник не указан'}</strong>
      {meta?.source === 'BANK' ? <><p>Поступления за 12 месяцев:</p><ol className={css.monthList}>{application.turnover_12m.map(month => <li key={month.month}>{month.month} — {formatMoney(month.amount)}</li>)}</ol><p className={css.muted}>Дата получения оборотов не передаётся в API</p></> : check?.status === 'FAILED' ? <p>Источник не ответил ({check.attempts} попытки)</p> : check?.status === 'PENDING' ? <p>Ожидаем ответ источника</p> : <>
        {meta?.fields.map(field => <p key={field.path}>{field.label} — {displayValue(fieldValue(check?.response, field.path), field.money)}</p>)}
        <p className={css.muted}>{check?.fetched_at ? `Получено ${formatAt(check.fetched_at)}` : 'Время получения не передано'}</p>
      </>}
      {meta?.average && <p>Средний оборот — {decision.policy ? formatMoney(decision.policy.avg_turnover) : 'нет в ответе'}</p>}
      <p>Правило начисления: {factor.rule}</p>
    </div>}</Collapse>
  </div>;
}

export default function Factors({ application, decision }: { application: BankApplication; decision: BankDecision }) {
  const known = new Set(factorGroups.flatMap(g => g.codes));
  const extras = decision.factors.filter(f => !known.has(f.code));
  const groups = [...factorGroups, ...(extras.length ? [{ title: 'Другие факторы', codes: extras.map(f => f.code) }] : [])];
  return <section className={css.factors} aria-label="Факторы оценки"><div className={css.sectionHeading}><h2>Факторы оценки</h2><span className={css.muted}>{decision.factors.length} признаков · правила v{decision.config_version}</span></div>
    {decision.factors.length ? <><div className={css.factorColumns} aria-hidden="true"><span>Признак</span><span>Значение</span><span>Баллы</span><span>из макс.</span></div>
      {groups.map(group => {
        const factors = decision.factors.filter(f => group.codes.includes(f.code));
        if (!factors.length) return null;
        const points = factors.reduce((sum, f) => sum + f.points, 0), max = factors.reduce((sum, f) => sum + f.max_points, 0);
        return <div key={group.title} role="group" aria-label={group.title}><div className={css.groupRow}><strong>{group.title}</strong><span /><Bar points={points} max={max} total /><strong className={css.points}>{points} / {max}</strong></div>{factors.map(f => <Factor key={f.code} factor={f} application={application} decision={decision} />)}</div>;
      })}
    </> : <p className={css.muted}>Оценка не рассчитана. Проверьте сведения и сработавшие правила.</p>}
    {decision.score !== null && <div className={css.total}><strong>Итого {decision.score} / 100</strong><span>Класс {decision.grade}</span><Bar points={decision.score} max={100} total /></div>}
  </section>;
}
