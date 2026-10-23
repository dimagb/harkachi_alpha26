import { stageStatusColor, stageStatusIcon } from '../../ui/status';
import { formatAt, statusText } from './presentation';
import type { Application } from './presentation';
import css from './Card.module.css';

export default function Timeline({ timeline }: { timeline: Application['timeline'] }) {
  return <ol className={css.timeline} aria-label="Этапы заявки">
    {timeline.map((step, index) => {
      const tone = stageStatusColor(step.status);
      const icon = stageStatusIcon(step.status);
      const pending = step.status === 'pending';
      const active = step.status === 'current' || step.status === 'action_required';
      const shade = step.status === 'current' ? 9 : step.status === 'action_required' ? 4 : step.status === 'cancelled' ? 5 : 6;
      return <li key={step.stage_code} data-status={step.status} aria-current={active ? 'step' : undefined}>
        <div className={css.rail}>
          <span className={css.node} aria-hidden="true" style={{
            background: pending ? 'var(--cc-paper)' : `var(--mantine-color-${tone}-${shade})`,
            color: pending ? 'var(--mantine-color-gray-7)' : step.status === 'action_required' ? 'var(--cc-ink)' : 'var(--cc-paper)',
            border: pending ? '1.5px solid var(--mantine-color-gray-4)' : undefined,
            boxShadow: active ? `0 0 0 var(--cc-stage-halo) var(--mantine-color-${tone}-${step.status === 'current' ? 2 : 1})` : undefined,
            fontSize: pending ? 'var(--mantine-font-size-xs)' : undefined, fontWeight: pending ? 500 : 600,
          }}>{step.status === 'done' ? <span className={css.check} /> : icon === 'number' ? index + 1 : icon}</span>
          {index < timeline.length - 1 && <span className={css.line} aria-hidden="true" style={{ background: step.status === 'done' ? 'var(--cc-ok)' : 'var(--cc-line)' }} />}
        </div>
        <div className={css.stageCopy}>
          <span className={css.stageTitle} style={{ fontWeight: active || step.status === 'failed' ? 600 : 400, color: pending ? 'var(--cc-ink-2)' : 'var(--cc-ink)' }}>{step.title}</span>
          <span className={css.stageMeta} style={{ color: step.status === 'current' ? 'var(--cc-ink)' : pending ? 'var(--cc-ink-2)' : `var(--mantine-color-${tone}-7)` }}>{step.status === 'done' && step.at ? <time dateTime={step.at}>{formatAt(step.at)}</time> : statusText[step.status]}</span>
        </div>
      </li>;
    })}
  </ol>;
}
