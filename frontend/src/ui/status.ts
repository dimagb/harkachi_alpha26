import type { components } from '../api/schema';
import { theme } from '../theme';

const stageColors = {
  done: 'ok',
  current: 'gray',
  action_required: 'wait',
  failed: 'stop',
  cancelled: 'gray',
  pending: 'gray',
} as const satisfies Record<components['schemas']['TimelineItem']['status'], string>;

export function stageStatusColor(status: components['schemas']['TimelineItem']['status']) {
  return stageColors[status];
}

export function stageStatusIcon(status: components['schemas']['TimelineItem']['status']) {
  return { done: '✓', current: 'number', action_required: '!', failed: '×', cancelled: '×', pending: 'number' }[status];
}

export function formatMoney(v: number): string {
  return theme.other!.money(v);
}
