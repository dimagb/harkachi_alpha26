import { Button } from '@mantine/core';
import { useState } from 'react';
import { api } from '../../../api/client';
import { formatMoney } from '../../../ui/status';
import type { SubmitProps } from './SubmitSection';
import OtpConfirm, { type SigningFailure } from './OtpConfirm';
import card from '../Card.module.css';
import css from './SigningSection.module.css';
import decisionCss from './DecisionSection.module.css';

export default function SigningSection({ application, onUpdate, onReload, onMessage }: Omit<SubmitProps, 'companyKind'>) {
  const [confirming, setConfirming] = useState<string | null>(null);
  if (application.state !== 'SIGNING' && application.state !== 'SIGNED') return null;
  const offer = application.offer;
  const next = application.state === 'SIGNING' && application.allowed_actions.includes('SIGN') ? application.parties.find((party) => party.is_me && !party.signed) : undefined;
  async function failure(error: SigningFailure) {
    if (error.status === 403 || error.status === 409) { onMessage(error.message); await onReload(); }
  }
  return <section id="signing" aria-label="Подписание" className={`${card.card} ${css.section}`}>
    <h3 className={card.title}>Условия договора</h3>
    {offer && <div className={card.figures}>
      {[['Сумма', formatMoney(offer.amount)], ['Срок', `${offer.term_months} мес.`], ['Ставка', `${offer.rate.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`], ['Платёж в месяц', offer.monthly_payment === null ? 'Проценты — только за использованные дни' : formatMoney(offer.monthly_payment)]].map(([label, value]) => <div className={card.figure} key={label}><span className={css.muted}>{label}</span><span className={card.figureValue}>{value}</span></div>)}
    </div>}
    {offer && application.state === 'SIGNING' && application.parties.some((party) => !party.signed) && <p className={decisionCss.expiry}>Подписать нужно до {new Date(offer.expires_at).toLocaleDateString('ru-RU', { timeZone: 'Europe/Moscow' })}</p>}
    <p>Подписание — простой электронной подписью: код из СМС</p>
    <h3 className={card.title}>Участники</h3>
    <ul className={css.parties}>{application.parties.map((party) => <li key={party.id} className={css.party}>
      <strong>{party.role === 'BORROWER_SIGNATORY' ? 'Заёмщик — подписант компании' : 'Поручитель'}</strong>
      <p>{party.full_name} {party.is_me && <span className={css.muted}>это вы</span>}</p>
      <span className={css.badge} data-signed={party.signed}>{party.signed ? '✓ Подписано' : 'Ждёт подписи'}</span>
      {next?.id === party.id && <>
        {party.role === 'GUARANTOR' && <p>Вместе с поручительством вы подписываете согласия на обработку персональных данных и запрос в бюро кредитных историй как поручитель</p>}
        <div className={css.actions}><Button data-signing-action className={card.cta} onClick={() => setConfirming(party.id)}>{party.role === 'BORROWER_SIGNATORY' ? 'Подписать договор' : 'Подписать поручительство'}</Button></div>
        {confirming === party.id && <OtpConfirm key={party.id} applicationId={application.id} purpose={party.role === 'BORROWER_SIGNATORY' ? 'OFFER' : 'GUARANTEE'} partyId={party.id} confirmLabel="Подтвердить подпись" onFailure={failure} onConfirm={async (otp) => {
          onMessage('');
          const result = await api.POST('/applications/{id}/sign', { params: { path: { id: application.id } }, body: { ...otp, party_id: party.id } });
          if (result.error) throw Object.assign(new Error(result.response.status === 501 ? 'Подписание пока недоступно, попробуйте позже' : result.error.error.message), { status: result.response.status, code: result.error.error.code });
          if (result.data) { setConfirming(null); onUpdate(result.data); }
        }} />}
      </>}
    </li>)}</ul>
    {application.state === 'SIGNED' ? <p role="status">Договор подписан, готовим выдачу</p> : application.parties.some((party) => !party.is_me && !party.signed) && <p role="status">Ждём подписи остальных участников</p>}
  </section>;
}
