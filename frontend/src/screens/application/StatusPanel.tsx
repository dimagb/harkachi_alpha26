import { Button, Paper, SimpleGrid, Stack, Text } from '@mantine/core';
import { Link } from 'react-router';
import { stageStatusColor } from '../../ui/status';
import type { Application, StageStatus } from './presentation';

const actions: Partial<Record<Application['allowed_actions'][number], [string, string]>> = {
  SUBMIT: ['Подписать и отправить', '#submit'], REQUEST_SIGNATURE: ['Отправить на подпись директору', '#submit'],
  ANSWER_INFO_REQUEST: ['Ответить банку', '#info-request'], ACCEPT_OFFER: ['Посмотреть предложение', '#decision'],
  SIGN: ['Подписать договор', '#signing'], NEW_APPLICATION: ['Подать новую заявку', '/app/applications/new'],
};
export default function StatusPanel({ application, status }: { application: Application; status: StageStatus }) {
  const action = application.allowed_actions.map((code) => actions[code]).find((item) => !!item);
  const approved = application.state === 'OFFER_ISSUED' && application.offer?.kind === 'APPROVED';
  const tone = approved ? 'ok' : stageStatusColor(status);
  const shade = status === 'current' && !approved ? 9 : status === 'cancelled' ? 5 : 6;
  return <Paper component="section" aria-label="Что происходит с заявкой" p="lg" radius="md" data-tone={tone} style={{ background: `var(--mantine-color-${tone}-0)`, borderLeft: `4px solid var(--mantine-color-${tone}-${shade})` }}>
    <SimpleGrid cols={{ base: 1, md: action ? 3 : 2 }} spacing="lg" style={{ alignItems: 'end' }}>
      <Stack gap={4} style={{ alignSelf: 'start' }}><Text size="sm" c="dimmed" fw={500}>Что происходит</Text><Text>{application.stage.what_happens}</Text></Stack>
      <Stack gap={4} style={{ alignSelf: 'start' }}><Text size="sm" c="dimmed" fw={500}>Что от вас нужно</Text><Text>{application.stage.what_to_do ?? 'Ничего, мы сообщим, когда понадобится ваше участие'}</Text></Stack>
      {action && <Button component={Link} to={action[1]} h="auto" py="sm" styles={{ label: { whiteSpace: 'normal' } }}>{action[0]}</Button>}
    </SimpleGrid>
  </Paper>;
}
