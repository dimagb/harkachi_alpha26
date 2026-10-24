import { Collapse } from '@mantine/core';
import { Fragment, useState } from 'react';
import { formatMoney } from '../../../ui/status';
import { responseLabels } from '../factorMeta';
import { formatAt, sourceLabels, type BankApplication } from '../labels';
import css from './Underwriter.module.css';

export function fieldValue(response: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((current, key) => current && typeof current === 'object' && key in current ? (current as Record<string, unknown>)[key] : undefined, response);
}
export function displayValue(value: unknown, money = false): string {
  if (value === undefined || value === null) return 'нет в ответе';
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
  if (typeof value === 'number') return money ? formatMoney(value) : new Intl.NumberFormat('ru-RU').format(value);
  if (Array.isArray(value)) return value.length ? value.map(v => displayValue(v, money)).join('; ') : 'Нет';
  if (typeof value === 'object') return Object.entries(value).map(([key, v]) => `${responseLabels[key] ?? key}: ${displayValue(v, /balance|payment|overdue|debt|_sum/.test(key))}`).join('; ');
  const statuses: Record<string, string> = { ACTIVE: 'Действует', LIQUIDATING: 'Ликвидируется', LIQUIDATED: 'Ликвидирована', MICRO: 'Микропредприятие', SMALL: 'Малое предприятие', MEDIUM: 'Среднее предприятие', OOO: 'ООО', IP: 'ИП', FULL: 'Полный отчёт', INFO: 'Информационная часть', CREDIT: 'Кредит' };
  return statuses[String(value)] ?? String(value);
}
function summary(check: BankApplication['external_checks'][number]) {
  const response = check.response;
  if (!response) return 'Сведения пока не получены';
  if (check.source === 'EGRUL') return `${displayValue(response.status)} · ОКВЭД ${displayValue(response.okved_main)}`;
  if (check.source === 'BKI') return `Текущая просрочка: ${displayValue(fieldValue(response, 'summary.current_overdue_total'), true)} · запросов за 30 дней: ${displayValue(fieldValue(response, 'summary.inquiries_30d'))}`;
  return `Налоговый долг: ${displayValue(response.tax_debt, true)}`;
}

export default function Sources({ application }: { application: BankApplication }) {
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  return <section className={css.section} aria-label="Сведения"><h2>Сведения</h2><div>
    {application.external_checks.map(check => <div key={check.source} className={css.source}>
      <button className={css.sourceButton} aria-expanded={!!opened[check.source]} onClick={() => setOpened(previous => ({ ...previous, [check.source]: !previous[check.source] }))}>
        <span className={css.sourceIcon} data-tone={check.status === 'OK' ? 'ok' : check.status === 'FAILED' ? 'stop' : 'wait'} aria-hidden="true">{check.status === 'OK' ? '✓' : check.status === 'FAILED' ? '!' : '…'}</span><strong>{sourceLabels[check.source]}</strong><span className={css.muted}>{summary(check)}</span><span className={css.sourceStatus} data-tone={check.status === 'OK' ? 'ok' : 'stop'}>{check.status === 'FAILED' ? `Не ответил (${check.attempts} попытки)` : check.status === 'PENDING' ? 'Ожидаем' : check.fetched_at ? `Получено ${formatAt(check.fetched_at)}` : 'Получено'}</span><span aria-hidden="true">{opened[check.source] ? '⌄' : '›'}</span>
      </button>
      <Collapse expanded={!!opened[check.source]} transitionDuration={120}>{opened[check.source] && <dl className={css.sourceDetails}>{check.response ? Object.entries(check.response).map(([key, value]) => <Fragment key={key}><dt>{responseLabels[key] ?? key}</dt><dd>{displayValue(value, /balance|payment|overdue|debt|_sum/.test(key))}</dd></Fragment>) : <><dt>Состояние источника</dt><dd>{check.status === 'FAILED' ? `Источник не ответил (${check.attempts} попытки)` : 'Ожидаем ответ'}</dd></>}</dl>}</Collapse>
    </div>)}
  </div></section>;
}
