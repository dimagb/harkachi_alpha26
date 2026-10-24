import { Button, Group, Modal } from '@mantine/core';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import { api } from '../../../api/client';
import type { components } from '../../../api/schema';
import { formatMoney } from '../../../ui/status';
import KeyFigures from '../KeyFigures';
import card from '../Card.module.css';
import css from './DecisionSection.module.css';

type Schema = components['schemas'];
type Application = Schema['ApplicationClient'];
type Props = { application: Application; product?: Schema['Product']; companyKind?: string; userId: string; onUpdate: (application: Application) => void; onReload: () => Promise<unknown>; onMessage: (message: string) => void };
const date = (value: string) => new Date(value).toLocaleDateString('ru-RU', { timeZone: 'Europe/Moscow' });

export default function DecisionSection({ application, product, companyKind, userId, onUpdate, onReload, onMessage }: Props) {
  const offer = application.offer;
  const [confirm, setConfirm] = useState(false);
  const requested = offer?.kind === 'COUNTER' ? offer.requested : null;
  const estimate = useQuery({ queryKey: ['requested-calculator', application.id, userId, application.product_code, requested?.amount, requested?.term_months], queryFn: async ({ signal }) => {
    const result = await api.POST('/calculator', { body: { product_code: application.product_code, amount: requested!.amount, term_months: requested!.term_months }, signal });
    if (result.error || !result.data) throw new Error('Не удалось рассчитать платёж');
    return result.data;
  }, enabled: !!requested && offer?.status === 'ACTIVE', retry: false, staleTime: Infinity });
  const action = useMutation({ mutationFn: async (kind: 'accept' | 'reject') => {
    onMessage('');
    const params = { path: { id: application.id } };
    const result = kind === 'accept'
      ? await api.POST('/applications/{id}/offer/accept', { params, body: { offer_version: offer!.version } })
      : await api.POST('/applications/{id}/offer/reject', { params });
    if (result.error) {
      const code = result.error.error.code;
      onMessage(code === 'OFFER_EXPIRED' ? 'Срок предложения истёк' : code === 'CONFLICT_VERSION' ? 'Условия изменились — проверьте их ещё раз' : result.response.status === 501 ? 'Действие пока недоступно, попробуйте позже' : result.error.error.message);
      if (result.response.status === 409) await onReload();
    } else if (result.data) onUpdate(result.data);
  }, onSettled: () => setConfirm(false), onError: () => onMessage('Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.') });

  if (application.state === 'DECLINED') {
    const reason = application.client_reason;
    return <section id="decision" aria-label="Решение банка" className={css.section}>
      {reason && <section className={css.reason} aria-label="Причина отказа">
        <div className={css.reasonCopy}><span className={css.reasonLabel}>Причина</span>{reason.category && <h3 className={card.title}>{reason.category}</h3>}<p>{reason.text}</p></div>
        <div className={css.reasonCopy}><h3 className={css.smallTitle}>Что можно сделать</h3><p>{reason.action ?? 'Можно подать новую заявку'}</p>{reason.retry_after && !/\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}/.test(reason.action ?? '') && <p>Подать новую заявку можно с {date(reason.retry_after)}</p>}</div>
      </section>}
    </section>;
  }
  if (application.state !== 'OFFER_ISSUED' || !offer || offer.status !== 'ACTIVE') return null;
  const canAccept = application.allowed_actions.includes('ACCEPT_OFFER');
  const buttons = canAccept ? <div className={css.actions}>
    <Button className={card.cta} loading={action.isPending && action.variables === 'accept'} disabled={action.isPending} onClick={() => action.mutate('accept')}>Принять предложение</Button>
    {application.allowed_actions.includes('REJECT_OFFER') && <Button className={card.cta} variant="light" color="gray" disabled={action.isPending} onClick={() => setConfirm(true)}>Отказаться</Button>}
  </div> : <p className={css.signatory}>Принять предложение может руководитель или сотрудник с правом подписи</p>;
  return <section id="decision" aria-label="Решение банка" className={css.section}>
    {offer.kind === 'COUNTER' && <section className={card.card} aria-label="Сравнение условий">
      {offer.counter_reason && <p className={css.counterReason}>{offer.counter_reason}</p>}
      <div className={css.comparison}>
        {requested && <section aria-label="Вы просили" className={css.requested}><h3 className={css.smallTitle}>Вы просили</h3><span className={css.compareAmount}>{formatMoney(requested.amount)}</span><dl className={css.compareDetails}><dt>Срок</dt><dd>{requested.term_months} мес.</dd><dt>Платёж в месяц</dt><dd>{estimate.data?.monthly_payment != null ? `около ${formatMoney(estimate.data.monthly_payment)}` : application.product_code === 'OVERDRAFT' ? 'Проценты — только за использованные дни' : estimate.isError ? 'Расчёт недоступен' : 'Рассчитываем…'}</dd></dl>{estimate.isError && <Button variant="default" onClick={() => void estimate.refetch()}>Повторить расчёт</Button>}</section>}
        <section aria-label="Мы предлагаем" className={css.proposed}><h3 className={css.smallTitle}>Мы предлагаем</h3><span className={css.compareAmount}>{formatMoney(offer.amount)}</span><dl className={css.compareDetails}><dt>Срок</dt><dd>{offer.term_months} мес.</dd><dt>Ставка</dt><dd>{offer.rate.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} %</dd><dt>Платёж в месяц</dt><dd>{offer.monthly_payment === null ? 'Проценты — только за использованные дни' : formatMoney(offer.monthly_payment)}</dd></dl></section>
      </div>
      {companyKind === 'OOO' && product?.requires_guarantor_ooo && <p className={css.guarantor}>Для ООО нужен поручитель — учредитель с долей больше 50%. Поручительство подписывается на следующем шаге</p>}
    </section>}
    <div className={css.offerColumns}>
      <section aria-label="Условия" className={card.card}><h3 className={card.title}>Условия</h3><KeyFigures application={application} error={false} onRetry={() => {}} offerOnly /><p className={css.expiry}>Предложение действует до {date(offer.expires_at)}</p>{buttons}</section>
      <section aria-label="Почему одобрили" className={`${card.card} ${css.explanation}`}><h3 className={card.title}>Почему одобрили</h3><ul className={css.reasons}>{offer.explanation.map((text, index) => <li key={index}><span className={css.checkCircle} aria-hidden="true"><span className={card.check} /></span><span>{text}</span></li>)}</ul></section>
    </div>
    <Modal opened={confirm} onClose={() => { if (!action.isPending) setConfirm(false); }} title="Отказаться от предложения?" centered>
      <p>Заявка будет закрыта, это действие нельзя отменить</p><Group justify="flex-end"><Button variant="default" disabled={action.isPending} onClick={() => setConfirm(false)}>Вернуться</Button><Button loading={action.isPending} onClick={() => action.mutate('reject')}>Отказаться</Button></Group>
    </Modal>
  </section>;
}

export function DecisionLinks({ application }: { application: Application }) {
  return <div className={css.actions}>{application.allowed_actions.includes('NEW_APPLICATION') && <Button component={Link} to="/app/applications/new" className={card.cta}>Подать новую заявку</Button>}<Button component={Link} to="/app" variant="light" color="gray" className={card.cta}>Вернуться к заявкам</Button></div>;
}
