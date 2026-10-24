import { Button, Modal, NumberInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../../api/client';
import type { components } from '../../../api/schema';
import css from '../Journal.module.css';

export default function TimeShiftModal({ application, onClose }: { application: components['schemas']['BankListItem']; onClose: () => void }) {
  const [days, setDays] = useState<string | number>(31);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const client = useQueryClient();
  async function submit() {
    if (typeof days !== 'number' || !Number.isInteger(days) || days < 1 || days > 400) { setError('Введите целое число от 1 до 400'); return; }
    setSaving(true); setError('');
    try {
      const { data, error: failure, response } = await api.POST('/demo/time-shift', { body: { application_id: application.id, days } });
      if (response.status === 403 || response.status === 404) { setError('Демо-режим выключен на сервере'); return; }
      if (failure || !data) { setError(failure?.error.message ?? 'Не удалось перемотать время. Повторите попытку'); return; }
      notifications.show({ color: 'gray', message: data.expired_now ? 'Срок истёк — заявка закрыта' : `Сроки сдвинуты на ${days} дн.` });
      await client.invalidateQueries({ queryKey: ['bank'] });
      onClose();
    } catch { setError('Не удалось перемотать время. Проверьте соединение и повторите попытку'); }
    finally { setSaving(false); }
  }
  return <Modal opened onClose={() => { if (!saving) onClose(); }} title={`Перемотка времени · заявка № ${application.number}`} closeButtonProps={{ 'aria-label': 'Закрыть' }}>
    <p>Только для демонстрации: сдвигает сроки заявки назад, как будто прошло N дней</p>
    <form onSubmit={event => { event.preventDefault(); void submit(); }} noValidate>
      <NumberInput label="Дней" min={1} max={400} clampBehavior="none" allowDecimal={false} value={days} onChange={setDays} error={error || undefined} disabled={saving} />
      <div className={css.actions}><Button variant="default" disabled={saving} onClick={onClose}>Отмена</Button><Button color="gray" type="submit" loading={saving}>Перемотать</Button></div>
    </form>
  </Modal>;
}
