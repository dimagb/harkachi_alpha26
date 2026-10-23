import type { components } from '../api/schema';
import { theme } from '../theme';

const stageColors = {
  done: 'ok',
  current: 'flow',
  action_required: 'wait',
  failed: 'stop',
  cancelled: 'gray',
  pending: 'gray',
} as const satisfies Record<components['schemas']['TimelineItem']['status'], string>;

export function stageStatusColor(status: components['schemas']['TimelineItem']['status']) {
  return stageColors[status];
}

export function formatMoney(v: number): string {
  return theme.other!.money(v);
}
