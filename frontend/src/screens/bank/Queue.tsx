import { Button, Group, Loader } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router';
import { formatMoney } from '../../ui/status';
import { api } from '../../api/client';
import { productLabels, routeLabels, waitingTime } from './labels';
import css from './Bank.module.css';
import ui from './Journal.module.css';
import card from '../application/Card.module.css';

export default function Queue() {
  const queue = useQuery({ queryKey: ['bank', 'queue'], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/underwriting/queue', { signal });
    if (error || !data) throw new Error(error?.error.message ?? 'Не удалось загрузить очередь');
    return data;
  }, retry: 1, refetchInterval: 10000 });
  const navigate = useNavigate();
  return <div className={card.page}><header className={`${card.header} ${ui.pageHeading}`}><h1>Очередь</h1><p>Заявки, которым нужно решение специалиста</p></header>
    {queue.isPending ? <div className={card.card}><Group role="status"><Loader size="sm" />Загружаем очередь…</Group></div> : queue.isError ? <div className={card.card} role="alert"><p>Не удалось загрузить очередь</p><Button w="fit-content" variant="default" onClick={() => void queue.refetch()}>Повторить</Button></div> : !queue.data.length ? <div className={card.card}><p>Очередь пуста. Новые заявки появятся здесь автоматически</p><Button variant="default" w="fit-content" onClick={() => void queue.refetch()}>Обновить очередь</Button></div> :
      <div className={ui.tableScroll} tabIndex={0} role="region" aria-label="Прокрутка очереди"><table className={ui.table} aria-label="Очередь заявок"><thead><tr>{['№', 'Компания', 'Продукт', 'Сумма', 'Оценка', 'Почему здесь', 'Ждёт'].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead><tbody>
        {queue.data.map(item => <tr className={ui.applicationRow} tabIndex={0} key={item.id} onKeyDown={event => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); void navigate(`/bank/applications/${item.id}`); } }} onClick={event => { if (!(event.target as Element).closest('a')) void navigate(`/bank/applications/${item.id}`); }}>
          <td><Link to={`/bank/applications/${item.id}`} aria-label={`Открыть заявку № ${item.number}`}>{item.number}</Link></td><td><span className={css.companyName}>{item.company_name}</span><span className={css.muted}>{item.company_kind === 'IP' ? 'ИП' : 'ООО'}</span></td><td>{productLabels[item.product_code]}</td><td className={css.money}>{formatMoney(item.amount)}</td><td><span className={css.grade} data-tone={item.grade === 'A' || item.grade === 'B' ? 'ok' : item.grade === 'D' ? 'stop' : 'wait'}>{item.grade ?? '—'}</span></td><td>{routeLabels[item.route_reason]}</td><td className={css.money}>{waitingTime(item.waiting_since, queue.dataUpdatedAt)}</td>
        </tr>)}
      </tbody></table></div>}
  </div>;
}
