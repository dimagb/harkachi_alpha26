import { Button } from '@mantine/core';
import { useState } from 'react';
import { api } from '../../../api/client';
import type { components } from '../../../api/schema';
import card from '../Card.module.css';
import css from './SigningSection.module.css';
import { consents } from './consents';
import OtpConfirm, { type SigningFailure } from './OtpConfirm';

export type SubmitProps = { application: components['schemas']['ApplicationClient']; companyKind?: string; onUpdate: (application: components['schemas']['ApplicationClient']) => void; onReload: () => Promise<unknown>; onMessage: (message: string) => void };
export default function SubmitSection({ application, companyKind, onUpdate, onReload, onMessage }: SubmitProps) {
  const [checked, setChecked] = useState({ pdn: false, bki: false, auto_decision: false });
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  if (application.state !== 'DRAFT') return null;
  const canSubmit = application.allowed_actions.includes('SUBMIT');
  const canRequest = application.allowed_actions.includes('REQUEST_SIGNATURE');
  const ready = checked.pdn && checked.bki;
  async function failure(error: SigningFailure) {
    if (error.status === 403 || error.status === 409) { onMessage(error.message); await onReload(); }
  }
  async function submit(otp: { otp_id: string; code: string }) {
    onMessage('');
    const result = await api.POST('/applications/{id}/submit', { params: { path: { id: application.id } }, body: { ...otp, consents: { pdn: true, bki: true, auto_decision: companyKind === 'IP' && checked.auto_decision } } });
    if (result.error) throw Object.assign(new Error(result.error.error.message), { status: result.response.status, code: result.error.error.code });
    if (result.data) onUpdate(result.data);
  }
  async function requestSignature() {
    setPending(true); onMessage('');
    try {
      const result = await api.POST('/applications/{id}/request-signature', { params: { path: { id: application.id } } });
      if (result.error) { onMessage(result.error.error.message); if (result.response.status === 403 || result.response.status === 409) await onReload(); }
      else if (result.data) onUpdate(result.data);
    } catch { onMessage('Не удалось отправить заявку на подпись. Проверьте соединение и попробуйте ещё раз.'); }
    finally { setPending(false); }
  }
  return <section id="submit" aria-label="Согласия и отправка" className={`${card.card} ${css.section}`}>
    <h3 className={card.title}>Согласия и отправка</h3>
    {canSubmit ? <>
      {consents.filter((consent) => companyKind === 'IP' || consent.key !== 'auto_decision').map((consent) => <section key={consent.key} aria-label={consent.title} className={css.document}>
        <h4 className={css.title}>{consent.title}</h4><p>{consent.text}</p>
        {!consent.required && <p className={css.muted}>Без него заявку рассмотрит специалист банка — это может занять до 1 рабочего дня</p>}
        <label className={css.checkbox}><input type="checkbox" aria-label={consent.label} checked={checked[consent.key]} onChange={(event) => { setChecked({ ...checked, [consent.key]: event.currentTarget.checked }); setConfirming(false); }} />Согласен{consent.required ? ' (обязательно)' : ' (необязательно)'}</label>
      </section>)}
      <div className={css.actions}><Button className={card.cta} disabled={!ready} onClick={() => setConfirming(true)}>Подписать и отправить</Button></div>
      {confirming && ready && <OtpConfirm applicationId={application.id} purpose="CONSENTS" confirmLabel="Подтвердить и отправить" onConfirm={submit} onFailure={failure} />}
    </> : application.awaiting_signature ? <><span className={css.badge}>Отправлено на подпись</span><p>Отправлено на подпись — руководитель увидит заявку в своём списке</p></> : <>
      <p>Отправить заявку может руководитель или сотрудник с правом подписи</p>
      {canRequest && <div className={css.actions}><Button loading={pending} disabled={pending} onClick={() => void requestSignature()}>Отправить на подпись директору</Button></div>}
    </>}
  </section>;
}
