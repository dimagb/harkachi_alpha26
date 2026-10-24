import { Button } from '@mantine/core';
import { Link, useNavigate } from 'react-router';
import { formatMoney } from '../../ui/status';
import { useBankQueue } from './BankLayout';
import { productLabels, routeLabels, waitingTime } from './labels';
import css from './Bank.module.css';

export default function Queue() {
  const queue = useBankQueue();
  const navigate = useNavigate();
  return <div className={css.stack}><header className={css.queueHeader}><h1>Очередь</h1><span className={css.muted}>Заявки, которым нужно решение специалиста</span></header>
    {queue.isPending ? <p role="status">Загружаем очередь…</p> : queue.isError ? <div role="alert"><p>Не удалось загрузить очередь</p><Button onClick={() => void queue.refetch()}>Повторить</Button></div> : !queue.data.length ? <p className={css.empty}>Очередь пуста. Новые заявки появятся здесь автоматически</p> :
      <div className={css.tableScroll}><table className={css.queueTable}><thead><tr>{['№', 'Компания', 'Продукт', 'Сумма', 'Оценка', 'Почему здесь', 'Ждёт'].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead><tbody>
        {queue.data.map(item => <tr key={item.id} onClick={event => { if (!(event.target as Element).closest('a')) void navigate(`/bank/applications/${item.id}`); }}>
          <td><Link to={`/bank/applications/${item.id}`} aria-label={`Открыть заявку № ${item.number}`}>{item.number}</Link></td><td><span className={css.companyName}>{item.company_name}</span><span className={css.muted}>{item.company_kind === 'IP' ? 'ИП' : 'ООО'}</span></td><td>{productLabels[item.product_code]}</td><td className={css.money}>{formatMoney(item.amount)}</td><td><span className={css.grade} data-tone={item.grade === 'A' || item.grade === 'B' ? 'ok' : item.grade === 'D' ? 'stop' : 'wait'}>{item.grade ?? '—'}</span></td><td>{routeLabels[item.route_reason]}</td><td className={css.money}>{waitingTime(item.waiting_since, queue.dataUpdatedAt)}</td>
        </tr>)}
      </tbody></table></div>}
  </div>;
}
