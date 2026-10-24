import { Button, Loader, Pagination } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../api/client';
import type { components } from '../../api/schema';
import type { BankApplication } from './labels';
import StateFilter from './journal/StateFilter';
import JournalTable from './journal/JournalTable';
import TimeShiftModal from './journal/TimeShiftModal';
import css from './Journal.module.css';
import card from '../application/Card.module.css';

export default function Journal() {
  const [state, setState] = useState<BankApplication['state'] | null>(null);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<components['schemas']['BankListItem'] | null>(null);
  const query = useQuery({ queryKey: ['bank', 'journal', state, page], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/bank/applications', { params: { query: { ...(state ? { state } : {}), page, size: 20 } }, signal });
    if (error || !data) throw new Error(error?.error.message ?? 'Не удалось загрузить журнал');
    return data;
  }, retry: 1 });
  const lastPage = query.data ? Math.max(1, Math.ceil(query.data.total / query.data.size)) : page;
  if (page > lastPage) setPage(lastPage);
  return <div className={card.page}>
    <header className={css.header}><div className={css.pageHeading}><h1>Журнал банка</h1><p>Все заявки и история их рассмотрения</p></div><StateFilter value={state} onChange={value => { setState(value); setPage(1); }} /></header>
    {query.isPending ? <div role="status" className={`${card.card} ${css.loading}`}><Loader size="sm" color="gray" /> Загружаем журнал…</div> : query.isError ? <div className={card.card} role="alert"><p>{query.error.message}</p><Button w="fit-content" variant="default" onClick={() => void query.refetch()}>Повторить</Button></div> : !query.data.items.length ? <div className={card.card}><p>Заявок с таким состоянием нет</p><Button variant="default" w="fit-content" onClick={() => { if (state) { setState(null); setPage(1); } else void query.refetch(); }}>{state ? 'Показать все заявки' : 'Обновить журнал'}</Button></div> : <>
      <JournalTable items={query.data.items} onTimeShift={setSelected} />
      <div className={css.pagination}><span>Показано {(query.data.page - 1) * query.data.size + 1}–{Math.min(query.data.page * query.data.size, query.data.total)} из {query.data.total}</span><Pagination color="gray" total={Math.ceil(query.data.total / query.data.size)} value={page} onChange={setPage} getItemProps={value => ({ 'aria-label': `Страница ${value}` })} getControlProps={control => ({ 'aria-label': control === 'next' ? 'Следующая страница' : 'Предыдущая страница' })} /></div>
    </>}
    {selected && <TimeShiftModal application={selected} onClose={() => setSelected(null)} />}
  </div>;
}
