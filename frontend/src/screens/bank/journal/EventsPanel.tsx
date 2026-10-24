import { Button, Loader } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { api } from '../../../api/client';
import { eventLabels, formatAt, stateLabels, type BankApplication } from '../labels';
import css from '../Journal.module.css';

export function EventsTable({ events }: { events: BankApplication['events'] }) {
  return <table className={css.table} aria-label="История заявки"><thead><tr>{['Время (Москва)', 'Кто', 'Событие', 'Из → в', 'Примечание'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>
    {events.map((event, i) => <tr key={i}><td><time dateTime={event.at}>{formatAt(event.at)}</time></td><td>{event.actor}</td><td>{eventLabels[event.event_type] ?? event.event_type}</td><td>{event.from_state ? stateLabels[event.from_state] : '—'} → {event.to_state ? stateLabels[event.to_state] : '—'}</td><td>{event.note ?? '—'}</td></tr>)}
    {!events.length && <tr><td colSpan={5}>Событий пока нет</td></tr>}
  </tbody></table>;
}
export default function EventsPanel({ id }: { id: string }) {
  const query = useQuery({ queryKey: ['bank', 'application', id], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/underwriting/applications/{id}', { params: { path: { id } }, signal });
    if (error || !data) throw new Error(error?.error.message ?? 'Не удалось загрузить события');
    return data;
  } });
  return <section aria-label="События по заявке" className={css.events}>
    <div className={css.links}><Link to={`/bank/applications/${id}`}>Открыть карточку</Link><Link to={`/bank/applications/${id}/protocol`} target="_blank" rel="noopener noreferrer">Печать протокола</Link></div>
    {query.isPending ? <div role="status"><Loader size="sm" color="gray" /> Загружаем события…</div> : query.isError ? <div role="alert"><p>{query.error.message}</p><Button onClick={() => void query.refetch()}>Повторить</Button></div> : <EventsTable events={query.data.events} />}
  </section>;
}
