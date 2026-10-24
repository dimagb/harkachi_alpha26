import { Button, Group, Modal, Textarea } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../../api/client';
import type { components } from '../../../api/schema';
import card from '../Card.module.css';
import css from './ObjectionBlock.module.css';

type Application = components['schemas']['ApplicationClient'];
export default function ObjectionBlock({ application, onUpdate, onReload, onMessage }: { application: Application; onUpdate: (application: Application) => void; onReload: () => Promise<unknown>; onMessage: (message: string) => void }) {
  const [opened, setOpened] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [failure, setFailure] = useState('');
  const send = useMutation({ mutationFn: async () => {
    onMessage('');
    const result = await api.POST('/applications/{id}/objection', { params: { path: { id: application.id } }, body: { text } });
    if (result.error) {
      if (result.response.status === 422) setError('Введите от 10 до 2000 символов');
      else setFailure(result.response.status === 501 ? 'Действие пока недоступно, попробуйте позже' : result.error.error.message);
      if (result.response.status === 409) await onReload();
    } else if (result.data) { setOpened(false); onUpdate(result.data); }
  }, onError: () => setFailure('Не удалось отправить обращение. Проверьте соединение и попробуйте ещё раз.') });
  if (application.objection) return <section aria-label="Пересмотр решения" className={css.block} data-status={application.objection.status} role="status">{application.objection.status === 'PENDING' ? 'Ваше обращение рассматривает специалист банка' : application.objection.outcome_text}</section>;
  if (!application.allowed_actions.includes('OBJECT')) return null;
  return <>
    <section aria-label="Пересмотр решения" className={css.block}><div className={css.copy}><strong>Не согласны с решением?</strong><span>Его пересмотрит специалист банка</span></div><Button variant="default" className={card.cta} onClick={() => { setFailure(''); setOpened(true); }}>Попросить пересмотр</Button></section>
    <Modal opened={opened} onClose={() => { if (!send.isPending) setOpened(false); }} title="Попросить пересмотр" centered>
      <form onSubmit={(event) => { event.preventDefault(); if (text.length < 10 || text.length > 2000 || text.trim().length < 10) { setError('Введите от 10 до 2000 символов'); return; } setError(''); setFailure(''); send.mutate(); }}>
        <Textarea label="Почему вы не согласны" value={text} onChange={(event) => setText(event.currentTarget.value)} description={`${text.length} / 2000`} error={error} rows={4} disabled={send.isPending} />
        {failure && <p role="alert">{failure}</p>}
        <Group justify="flex-end" mt="lg"><Button variant="default" disabled={send.isPending} onClick={() => setOpened(false)}>Вернуться</Button><Button type="submit" loading={send.isPending}>Отправить обращение</Button></Group>
      </form>
    </Modal>
  </>;
}
