import { Box, Text } from '@mantine/core';
import { stageStatusColor, stageStatusIcon } from '../../ui/status';
import { formatAt, statusText } from './presentation';
import type { Application } from './presentation';

export default function Timeline({ timeline }: { timeline: Application['timeline'] }) {
  return <>
    <style>{`
      .cc-timeline{display:grid;grid-template-columns:minmax(0,1fr);list-style:none;margin:0;padding:0}
      .cc-timeline li{display:grid;grid-template-columns:32px minmax(0,1fr);column-gap:16px;min-width:0}
      .cc-stage-rail{display:flex;flex-direction:column;align-items:center}
      .cc-stage-node{display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;width:24px;height:24px;margin:4px 0;border-radius:50%;font-size:14px;font-weight:600;font-variant-numeric:tabular-nums;border:1.5px solid transparent;transition:background-color 120ms,color 120ms}
      .cc-timeline li[data-status=current] .cc-stage-node,.cc-timeline li[data-status=failed] .cc-stage-node{width:32px;height:32px;margin:0}
      .cc-stage-line{flex:1;width:2px;min-height:16px;margin:4px 0;border-radius:1px;transition:background-color 320ms}
      .cc-stage-copy{padding:4px 0 20px;min-width:0}
      @media(min-width:768px){.cc-timeline{grid-template-columns:repeat(6,minmax(0,1fr))}.cc-timeline li{display:flex;flex-direction:column;gap:12px}.cc-stage-rail{flex-direction:row;height:32px}.cc-stage-line{height:2px;width:auto;min-height:0;margin:0 12px}.cc-stage-copy{padding:0 12px 0 0}}
      @media(prefers-reduced-motion:reduce){.cc-stage-node,.cc-stage-line{transition:none}}
    `}</style>
    <ol className="cc-timeline" aria-label="Этапы заявки">
      {timeline.map((step, index) => {
        const color = stageStatusColor(step.status);
        const icon = stageStatusIcon(step.status);
        const muted = step.status === 'pending';
        const shade = step.status === 'current' ? 9 : step.status === 'cancelled' ? 5 : 6;
        return <li key={step.stage_code} data-status={step.status} aria-current={step.status === 'current' || step.status === 'action_required' ? 'step' : undefined}>
          <div className="cc-stage-rail">
            <Box component="span" className="cc-stage-node" aria-hidden="true" style={{ background: muted ? 'var(--mantine-color-body)' : `var(--mantine-color-${color}-${shade})`, color: muted ? 'var(--mantine-color-gray-6)' : step.status === 'action_required' ? 'var(--mantine-color-gray-9)' : 'var(--mantine-color-white)', borderColor: muted ? 'var(--mantine-color-gray-3)' : 'transparent' }}>{icon === 'number' ? index + 1 : icon}</Box>
            {index < timeline.length - 1 && <span className="cc-stage-line" aria-hidden="true" style={{ background: step.status === 'done' ? 'var(--mantine-color-ok-6)' : 'var(--mantine-color-gray-2)' }} />}
          </div>
          <div className="cc-stage-copy">
            <Text fw={['current', 'action_required', 'failed'].includes(step.status) ? 600 : 400} c={muted ? 'dimmed' : 'gray.9'}>{step.title}</Text>
            <Text size="sm" c={step.status === 'current' ? 'gray.9' : muted ? 'dimmed' : `${color}.7`}>
              {step.status === 'done' && step.at ? <time dateTime={step.at}>{formatAt(step.at)}</time> : statusText[step.status]}
            </Text>
          </div>
        </li>;
      })}
    </ol>
  </>;
}
