import { Button } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { api } from '../../api/client';
import { formatMoney } from '../../ui/status';
import Timeline from '../application/Timeline';
import { useBankQueue } from './BankLayout';
import { formatAt, outcomeLabels, productLabels, routeLabels, waitingTime } from './labels';
import DecisionForm from './underwriter/DecisionForm';
import { Policy, Protocol, Rules, Turnover } from './underwriter/Details';
import Factors from './underwriter/Factors';
import Recommendation from './underwriter/Recommendation';
import Sources from './underwriter/Sources';
import css from './underwriter/Underwriter.module.css';

const finalStates = ['DECLINED', 'DISBURSED', 'WITHDRAWN', 'EXPIRED'];
export default function UnderwriterCard() {
  const { id = '' } = useParams();
  const [conflict, setConflict] = useState(false);
  const queue = useBankQueue();
  const query = useQuery({ queryKey: ['bank', 'application', id], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/underwriting/applications/{id}', { params: { path: { id } }, signal });
    if (error || !data) throw new Error(error?.error.message ?? 'Не удалось загрузить заявку');
    return data;
  }, refetchInterval: query => { const app = query.state.data; return app && (app.state === 'MANUAL_REVIEW' || finalStates.includes(app.state)) ? false : 5000; } });
  if (query.isPending) return <p role="status">Загружаем заявку…</p>;
  if (query.isError) return <div role="alert"><p>{query.error.message}</p><Button onClick={() => void query.refetch()}>Повторить</Button><Link to="/bank/queue">Вернуться в очередь</Link></div>;
  const application = query.data;
  const decision = application.decisions.find(d => d.kind === 'AUTO');
  const manual = application.decisions.find(d => d.kind === 'MANUAL');
  const route = decision?.route_reason;
  const queued = queue.data?.find(item => item.id === application.id);
  const evaluation = decision?.grade ? `${decision.grade}, ${decision.score ?? '—'} балла(ов)` : '';
  return <div className={css.card}>
    <header className={css.header}><div className={css.headerCopy}><div className={css.headerMeta}><span>Заявка № {application.number}</span>{queued && <span className={css.waiting}>Ждёт {waitingTime(queued.waiting_since)}</span>}<span>Поступила {formatAt(application.created_at)}</span></div><h1><span>{application.company.name} · {productLabels[application.product_code]}</span><span className={css.headerAmount}>{formatMoney(application.amount)}</span><span>/ {application.term_months} мес.</span></h1></div><div className={css.badges}>{route && <span className={css.badge} data-tone="wait">{routeLabels[route]}{evaluation ? route === 'GRADE_C' ? `: ${evaluation}` : ` · оценка ${evaluation}` : ''}</span>}{application.risk_flags.aml_flag && <span className={css.badge} data-tone="stop">Признаки AML</span>}{application.risk_flags.fraud_flag && <span className={css.badge} data-tone="stop">Признаки мошенничества</span>}</div></header>
    {conflict && <div role="alert" className={css.warning}>Заявка уже не на рассмотрении</div>}
    <section className={css.stages} aria-label="Этапы рассмотрения"><Timeline timeline={application.timeline} /><div className={css.statusPanel}><div><span className={css.caption}>Что происходит</span><span>{application.state === 'MANUAL_REVIEW' && route ? `${routeLabels[route]} — система не решает сама.` : application.stage.what_happens}</span></div><div><span className={css.caption}>Что нужно</span><strong>{application.state === 'MANUAL_REVIEW' ? 'Проверьте факторы и примите решение с комментарием.' : application.stage.what_to_do ?? 'Дополнительные действия специалиста не требуются.'}</strong></div></div></section>
    <div className={css.columns}><div className={css.left}>
      {decision && <Factors application={application} decision={decision} />}
      {decision && <Rules decision={decision} />}
      <Sources application={application} /><Turnover application={application} />{decision && <Policy decision={decision} />}
    </div><aside className={css.aside}>{decision && <Recommendation decision={decision} />}
      {application.state === 'MANUAL_REVIEW' ? <DecisionForm key={application.id} application={application} decision={decision} onConflict={() => { setConflict(true); void query.refetch(); void queue.refetch(); }} /> : manual ? <section className={css.section} aria-label="Решение принято"><h2>Решение принято</h2><strong>{outcomeLabels[manual.outcome]}</strong><p>{manual.comment}</p><span className={css.muted}>{manual.made_by} · {formatAt(manual.created_at)}</span><Link to="/bank/queue">Вернуться в очередь</Link></section> : <section className={css.section}><h2>{application.state === 'DECLINED' ? 'Решение системы' : 'Заявка обрабатывается'}</h2><p>{application.stage.what_happens}</p><Link to="/bank/queue">Вернуться в очередь</Link></section>}
    </aside></div><Protocol application={application} />
  </div>;
}
