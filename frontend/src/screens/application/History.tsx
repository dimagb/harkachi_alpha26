import { Paper, Stack, Text, Title } from '@mantine/core';
import { formatAt, statusText } from './presentation';
import type { Application } from './presentation';

export default function History({ timeline }: { timeline: Application['timeline'] }) {
  const history = timeline.filter((step) => step.at).sort((a, b) => Date.parse(b.at!) - Date.parse(a.at!));
  return <Paper component="section" aria-label="История заявки" withBorder p={{ base: 'md', sm: 'xl' }}><Stack gap="lg"><Title order={2} size="h3">История</Title>
    {history.length ? <Stack component="ol" aria-label="История этапов" gap={0} m={0} p={0} style={{ listStyle: 'none' }}>{history.map((step) => <Text component="li" key={step.stage_code} py="sm" style={{ borderTop: '1px solid var(--mantine-color-gray-2)' }}><Text component="time" dateTime={step.at!} c="dimmed" mr="sm">{formatAt(step.at!)}</Text>{step.title} — {statusText[step.status]}</Text>)}</Stack> : <Text c="dimmed">История появится после начала обработки заявки.</Text>}
  </Stack></Paper>;
}
