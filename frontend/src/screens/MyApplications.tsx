import { Badge, Button, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { api } from '../api/client';
import { useCompany } from '../company/CompanyContext';
import { stateLabels } from '../ui/labels';
import { formatMoney, stageStatusColor } from '../ui/status';

export default function MyApplications() {
  const { companyId } = useCompany();
  const products = useQuery({ queryKey: ['products'], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/products', { signal });
    if (error || !data) throw new Error('Не удалось загрузить продукты.');
    return data;
  }, retry: false });
  const applications = useQuery({ queryKey: ['applications', companyId], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/applications', { params: { query: { company_id: companyId! } }, signal });
    if (error || !data) throw new Error('Не удалось загрузить заявки.');
    return data;
  }, enabled: !!companyId, retry: false });
  const failed = products.isError || applications.isError;
  return <Stack gap="xl">
    <Title order={1}>Мои заявки</Title>
    {!companyId ? <Text>Для вашей учётной записи пока нет компании.</Text> : failed ? <Stack align="flex-start">
      <Text role="alert">Не удалось загрузить заявки. Попробуйте ещё раз.</Text>
      <Button variant="default" onClick={() => { void products.refetch(); void applications.refetch(); }}>Повторить</Button>
    </Stack> : products.isPending || applications.isPending ? <Group role="status"><Loader size="sm" /><Text>Загружаем заявки…</Text></Group> : <>
      {!applications.data.length ? <Paper withBorder p="xl"><Stack><Text fw={600}>Заявок пока нет</Text><Text c="dimmed">Выберите цель и узнайте, какие условия подойдут вашему бизнесу.</Text></Stack></Paper> :
        <Stack gap="md">{applications.data.map((item) => <Paper component={Link} to={`/app/applications/${item.id}`} key={item.id} withBorder p="lg" style={{ color: 'inherit', textDecoration: 'none' }}>
          <Stack gap="sm">
            <Group justify="space-between"><Text fw={600}>№ {item.number} · {products.data.find(({ code }) => code === item.product_code)?.name}</Text><Text fw={700}>{formatMoney(item.amount)}</Text></Group>
            <Group justify="space-between"><Group gap="xs"><Badge color={stageStatusColor('current')} variant="light">{item.stage.title}</Badge><Text size="sm" c="dimmed">{stateLabels[item.state]}</Text>{item.awaiting_signature && <Badge color={stageStatusColor('action_required')} variant="light">Ждёт подписи директора</Badge>}</Group><Text size="sm" c="dimmed">{new Date(item.updated_at).toLocaleDateString('ru-RU', { timeZone: 'UTC' })}</Text></Group>
          </Stack>
        </Paper>)}</Stack>}
      <Button component={Link} to="/app/applications/new" w="fit-content" maw="100%">Получить финансирование</Button>
    </>}
  </Stack>;
}
