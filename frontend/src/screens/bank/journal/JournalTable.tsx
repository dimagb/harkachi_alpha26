import { Button } from '@mantine/core';
import { Fragment, useState } from 'react';
import type { components } from '../../../api/schema';
import { formatMoney } from '../../../ui/status';
import { formatAt, productLabels, stateLabels } from '../labels';
import EventsPanel from './EventsPanel';
import css from '../Journal.module.css';

type Item = components['schemas']['BankListItem'];
function tone(state: Item['state']) {
  if (['OFFER_ISSUED', 'SIGNED', 'DISBURSED'].includes(state)) return 'ok';
  if (['INFO_REQUESTED', 'SIGNING'].includes(state)) return 'wait';
  return state === 'DECLINED' ? 'stop' : 'gray';
}
export default function JournalTable({ items, onTimeShift }: { items: Item[]; onTimeShift: (item: Item) => void }) {
  const [expanded, setExpanded] = useState<string[]>([]);
  const toggle = (id: string) => setExpanded(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);
  return <div className={css.tableScroll}><table className={css.table} aria-label="Заявки банка"><thead><tr>{['№', 'Компания', 'Продукт', 'Сумма', 'Состояние', 'Оценка', 'Обновлена', 'Демо'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>
    {items.map(item => <Fragment key={item.id}>
      <tr className={css.applicationRow} onClick={event => { if (!(event.target as Element).closest('button, a')) toggle(item.id); }}>
        <td><button type="button" className={css.number} aria-label={`События заявки № ${item.number}`} aria-expanded={expanded.includes(item.id)} aria-controls={`events-${item.id}`} onClick={() => toggle(item.id)}>{item.number}</button></td>
        <td><strong className={css.company}>{item.company_name}</strong><span className={css.muted}>{item.company_kind === 'IP' ? 'ИП' : 'ООО'}</span></td>
        <td>{productLabels[item.product_code]}</td><td className={css.money}>{formatMoney(item.amount)}</td><td><span className={css.badge} data-tone={tone(item.state)}>{stateLabels[item.state]}</span></td><td>{item.grade ?? '—'}</td><td className={css.money}><time dateTime={item.updated_at}>{formatAt(item.updated_at)}</time></td>
        <td>{['OFFER_ISSUED', 'SIGNING', 'INFO_REQUESTED'].includes(item.state) && <Button size="compact-xs" variant="subtle" color="gray" leftSection={<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></svg>} onClick={() => onTimeShift(item)}>Перемотать время · демо</Button>}</td>
      </tr>
      {expanded.includes(item.id) && <tr><td colSpan={8} id={`events-${item.id}`} className={css.expanded}><EventsPanel id={item.id} /></td></tr>}
    </Fragment>)}
  </tbody></table></div>;
}
