import { Divider, Stack, Text } from '@mantine/core';
import type { components } from '../../api/schema';
import { purposeLabels } from '../../ui/labels';
import { formatMoney } from '../../ui/status';
import type { Application } from './presentation';

export default function Details({ application, company }: { application: Application; company?: components['schemas']['MeResponse']['companies'][number]['company'] }) {
  return <Stack component="section" aria-label="Детали заявки" gap="md">
    <Divider /><Stack gap={4}><Text size="sm" c="dimmed">Цель</Text><Text>{application.purpose === 'OTHER' ? application.purpose_text : purposeLabels[application.purpose]}</Text></Stack>
    <Stack gap={4}><Text size="sm" c="dimmed">Выручка за год</Text><Text>{formatMoney(application.declared_revenue_year)}</Text></Stack>
    <Stack gap={4}><Text size="sm" c="dimmed">Компания</Text><Text>{company?.name ?? 'Сведения о компании недоступны'}</Text>{company && <Text c="dimmed">ИНН {company.inn}</Text>}</Stack>
  </Stack>;
}
