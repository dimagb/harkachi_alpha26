import { statusText } from './presentation';
import type { Application } from './presentation';
import css from './Card.module.css';

const completed: Record<Application['timeline'][number]['stage_code'], string> = {
  APPLICATION: 'Заявка отправлена', CHECK: 'Данные проверены', ASSESSMENT: 'Оценка завершена',
  DECISION: 'Решение готово', SIGNING: 'Договор подписан', DISBURSEMENT: 'Деньги зачислены',
};
const actionHistory: Partial<Record<Application['timeline'][number]['stage_code'], string>> = {
  CHECK: 'Банк попросил уточнить данные', DECISION: 'Предложение готово', SIGNING: 'Договор готов к подписанию',
};
export default function History({ timeline }: { timeline: Application['timeline'] }) {
  const history = timeline.filter((step) => step.at).sort((a, b) => Date.parse(b.at!) - Date.parse(a.at!));
  const options = { timeZone: 'Europe/Moscow' };
  return <section aria-label="История заявки" className={css.card}>
    <div className={css.historyHeader}><h3 className={css.title}>История</h3>{history[0]?.at && <span className={css.muted}>{new Date(history[0].at).toLocaleDateString('ru-RU', options)}</span>}</div>
    {history.length ? <ol aria-label="История этапов" className={css.history}>{history.map((step) => <li key={step.stage_code}>
      <time dateTime={step.at!}>{new Date(step.at!).toLocaleTimeString('ru-RU', { ...options, hour: '2-digit', minute: '2-digit' })}</time>
      <span style={{ fontWeight: step.status === 'action_required' ? 500 : 400 }}>{step.status === 'done' ? completed[step.stage_code] : step.status === 'failed' ? 'Банк отказал' : step.status === 'action_required' ? actionHistory[step.stage_code] ?? `${statusText[step.status]}: ${step.title}` : `${statusText[step.status]}: ${step.title}`}</span>
    </li>)}</ol> : <span className={css.muted}>История появится после начала обработки заявки.</span>}
  </section>;
}
