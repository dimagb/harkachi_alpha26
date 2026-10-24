import { Button } from '@mantine/core';
import { useEffect, useId, useRef, useState } from 'react';
import { api } from '../../../api/client';
import type { components } from '../../../api/schema';
import css from './SigningSection.module.css';

type Schema = components['schemas'];
export type SigningFailure = { status: number; code: string; message: string };
type Props = { applicationId: string; purpose: Schema['OtpRequest']['purpose']; partyId?: string; confirmLabel: string; onConfirm: (otp: { otp_id: string; code: string }) => Promise<void>; onFailure: (error: SigningFailure) => Promise<void> };
export default function OtpConfirm({ applicationId, purpose, partyId, confirmLabel, onConfirm, onFailure }: Props) {
  const [otp, setOtp] = useState<Schema['OtpResponse'] | null>(null);
  const [code, setCode] = useState('');
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const errorId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!otp) return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [otp]);
  const seconds = otp ? Math.max(0, Math.ceil((Date.parse(otp.expires_at) - now) / 1000)) : 0;
  const expired = seconds === 0;
  useEffect(() => {
    const target = expired ? requestRef.current : inputRef.current;
    target?.focus({ preventScroll: true });
    target?.scrollIntoView?.({ block: 'center' });
  }, [otp, expired]);
  async function run(action: () => Promise<void>) {
    setPending(true); setMessage('');
    try { await action(); } catch (error) {
      if (error instanceof Error && 'status' in error && typeof error.status === 'number' && 'code' in error && typeof error.code === 'string') {
        setMessage(error.message);
        if (error.code === 'OTP_INVALID') {
          setCode('');
          if (error.message.includes('недействителен или истёк')) setOtp(null);
        }
        await onFailure({ status: error.status, code: error.code, message: error.message });
      } else setMessage('Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
    } finally { setPending(false); }
  }
  async function requestCode() {
    const result = await api.POST('/applications/{id}/otp', { params: { path: { id: applicationId } }, body: { purpose, ...(partyId ? { party_id: partyId } : {}) } });
    if (result.error) throw Object.assign(new Error(result.error.error.message), { status: result.response.status, code: result.error.error.code });
    if (result.data) { setOtp(result.data); setCode(''); setNow(Date.now()); }
  }
  return <div className={css.otp}>
    {otp && seconds === 0 && <p role="status">Код истёк</p>}
    {(!otp || seconds === 0) ? <Button ref={requestRef} disabled={pending} loading={pending} onClick={() => void run(requestCode)}>{otp ? 'Получить новый код' : 'Получить код'}</Button> : <>
      <label className={css.input}>Код из SMS<input ref={inputRef} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} aria-invalid={!!message} aria-describedby={message ? errorId : undefined} onChange={(event) => setCode(event.currentTarget.value.replace(/\D/g, '').slice(0, 6))} /></label>
      {message && <p id={errorId} role="alert" className={css.error}>{message}</p>}
      <p className={css.muted}>Код действует ещё {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</p>
      {otp.demo_code && <div className={css.actions}><p>Демо-режим: код {otp.demo_code}</p><Button variant="light" color="gray" disabled={pending} onClick={() => setCode(otp.demo_code)}>Подставить</Button></div>}
      <Button disabled={pending || code.length !== 6} loading={pending} onClick={() => void run(() => onConfirm({ otp_id: otp.otp_id, code }))}>{confirmLabel}</Button>
    </>}
    {message && (!otp || seconds === 0) && <p id={errorId} role="alert" className={css.error}>{message}</p>}
  </div>;
}
