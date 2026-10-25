import { Button } from '@mantine/core';
import { Link } from 'react-router';
import { stageStatusColor } from '../../ui/status';
import type { Application, StageStatus } from './presentation';
import css from './Card.module.css';

const actions: Partial<Record<Application['allowed_actions'][number], [string, string]>> = {
  SUBMIT: ['Подписать и отправить', '#submit'], REQUEST_SIGNATURE: ['Отправить на подпись директору', '#submit'],
  ANSWER_INFO_REQUEST: ['Ответить на вопросы банка', '#info-request'], ACCEPT_OFFER: ['Посмотреть предложение', '#decision'],
  SIGN: ['Подписать договор', '#signing'], NEW_APPLICATION: ['Подать новую заявку', '/app/applications/new'],
};
export default function StatusPanel({ application, status }: { application: Application; status: StageStatus }) {
  const action = application.allowed_actions.map((code) => actions[code]).find((item) => !!item);
  const retryLater = action === actions.NEW_APPLICATION && application.state === 'DECLINED' && !!application.client_reason?.retry_after;
  const approved = application.state === 'OFFER_ISSUED' && application.offer?.kind === 'APPROVED';
  const tone = approved ? 'ok' : stageStatusColor(status);
  const shade = tone === 'wait' ? 4 : tone === 'gray' ? 9 : 6;
  const index = Math.max(0, application.timeline.findIndex((step) => step.stage_code === application.stage.code));
  return <section aria-label="Что происходит с заявкой" className={css.panel} data-tone={tone} data-action={!!action} style={{ background: `var(--mantine-color-${tone}-0)`, boxShadow: `inset 4px 0 0 var(--mantine-color-${tone}-${shade})` }}>
    <span aria-hidden="true" className={css.caret} style={{ left: `calc(${index} * 100% / 6 + var(--cc-stage-node) / 2 - 6px)` }} />
    <div className={css.panelCopy}><span className={css.panelLabel}>Что происходит</span><span className={css.panelText}>{application.stage.what_happens}</span></div>
    <div className={css.panelCopy}><span className={css.panelLabel} style={{ color: `var(--mantine-color-${tone}-7)` }}>Что от вас нужно</span><span className={css.panelText} style={{ fontWeight: 500 }}>{application.stage.what_to_do ?? 'Ничего, мы сообщим, когда понадобится ваше участие'}</span></div>
    {action && <Button component={Link} to={action[1]} variant={retryLater ? 'default' : undefined} className={css.cta} onClick={(event) => {
      if (!action[1].startsWith('#')) return;
      const section = document.getElementById(action[1].slice(1));
      if (action[1] === '#signing') {
        const target = section?.querySelector<HTMLInputElement>('input[autocomplete="one-time-code"]')
          ?? section?.querySelector<HTMLButtonElement>('[data-signing-action]');
        if (target) {
          event.preventDefault();
          target.focus({ preventScroll: true });
          target.scrollIntoView?.({ behavior: 'instant', block: 'center' });
          return;
        }
      }
      section?.scrollIntoView?.({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
    }}>{action[0]}</Button>}
  </section>;
}
