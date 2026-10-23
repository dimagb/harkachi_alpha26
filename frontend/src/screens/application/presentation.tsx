import type { components } from '../../api/schema';

export type Application = components['schemas']['ApplicationClient'];
export type StageStatus = components['schemas']['TimelineItem']['status'];
export const statusText: Record<StageStatus, string> = {
  done: 'Завершено', current: 'Идёт сейчас', action_required: 'Нужно ваше действие',
  pending: 'Ожидает', failed: 'Отказ', cancelled: 'Отменено',
};
export function formatAt(value: string) {
  const instant = new Date(value);
  const options = { timeZone: 'Europe/Moscow' };
  const time = instant.toLocaleTimeString('ru-RU', { ...options, hour: '2-digit', minute: '2-digit' });
  return instant.toLocaleDateString('ru-RU', options) === new Date().toLocaleDateString('ru-RU', options)
    ? time : `${instant.toLocaleDateString('ru-RU', { ...options, day: '2-digit', month: '2-digit' })} ${time}`;
}
