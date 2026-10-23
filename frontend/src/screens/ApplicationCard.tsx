import { Anchor, Badge, Button, Group, Loader, Modal, Notification, Paper, SimpleGrid, Stack, Text, Title, VisuallyHidden } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { api } from '../api/client';
import type { components } from '../api/schema';
import { stateLabels } from '../ui/labels';
import { formatMoney, stageStatusColor, stageStatusIcon } from '../ui/status';
import Timeline from './application/Timeline';
import StatusPanel from './application/StatusPanel';
import KeyFigures from './application/KeyFigures';
import Details from './application/Details';
import History from './application/History';

class CardError extends Error {
  constructor(readonly status: number) { super('Не удалось загрузить заявку. Попробуйте ещё раз.'); }
}
const polling = new Set(['SUBMITTED', 'VALIDATION', 'ENRICHMENT', 'ASSESSMENT', 'MANUAL_REVIEW', 'SIGNED']);
type CardProps = { companies: components['schemas']['MeResponse']['companies']; userId: string };
export default function ApplicationCard({ companies, userId }: CardProps) {
  const { id = '' } = useParams();
  return <CardContent key={`${userId}:${id}`} id={id} companies={companies} userId={userId} />;
}
function CardContent({ id, companies, userId }: CardProps & { id: string }) {
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const [message, setMessage] = useState('');
  const application = useQuery({ queryKey: ['application', id, userId], queryFn: async ({ signal }) => {
    const { data, error, response } = await api.GET('/applications/{id}', { params: { path: { id } }, signal });
    if (error || !data) throw new CardError(response.status);
    return data;
  }, retry: false, refetchInterval: (query) => query.state.data && !query.state.error && polling.has(query.state.data.state) ? 2000 : false });
  const data = application.data;
  const products = useQuery({ queryKey: ['products'], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/products', { signal });
    if (error || !data) throw new Error('Не удалось загрузить продукты.');
    return data;
  }, enabled: !!data, retry: false });
  const calculation = useQuery({ queryKey: ['card-calculator', id, userId], queryFn: async ({ signal }) => {
    const { data: estimate, error } = await api.POST('/calculator', { body: { product_code: data!.product_code, amount: data!.amount, term_months: data!.term_months }, signal });
    if (error || !estimate) throw new Error('Расчёт недоступен.');
    return estimate;
  }, enabled: !!data && !data.offer, retry: false, staleTime: Infinity, gcTime: 0, refetchOnWindowFocus: false, refetchOnReconnect: false });
  const withdraw = useMutation({ mutationFn: async () => {
    const result = await api.POST('/applications/{id}/withdraw', { params: { path: { id } } });
    if (result.error) {
      setMessage(result.response.status === 409 ? 'Заявка уже изменилась' : result.error.error.message);
      if (result.response.status === 409) await application.refetch();
      return null;
    }
    return result.data;
  }, onSuccess: (updated) => {
    setConfirm(false);
    if (!updated) return;
    queryClient.setQueryData(['application', id, userId], updated);
    void queryClient.invalidateQueries({ queryKey: ['applications', updated.company_id] });
  }, onError: () => { setConfirm(false); setMessage('Не удалось отозвать заявку. Проверьте соединение и попробуйте ещё раз.'); } });

  const pageHeading = <VisuallyHidden><Title order={1}>Карточка заявки</Title></VisuallyHidden>;
  if (application.isPending) return <>{pageHeading}<Group role="status"><Loader size="sm" /><Text>Загружаем заявку…</Text></Group></>;
  if (application.error instanceof CardError && application.error.status === 404) return <Stack>{pageHeading}<Title order={2}>Заявка не найдена</Title><Anchor component={Link} to="/app">К моим заявкам</Anchor></Stack>;
  if (application.isError || !data || products.isError) return <Stack align="flex-start">{pageHeading}<Text role="alert">Не удалось загрузить заявку. Попробуйте ещё раз.</Text><Button variant="default" onClick={() => { void application.refetch(); if (products.isError) void products.refetch(); }}>Повторить</Button><Anchor component={Link} to="/app">К моим заявкам</Anchor></Stack>;
  const current = data.timeline.find((step) => step.stage_code === data.stage.code);
  const status = current?.status ?? 'pending';
  const color = stageStatusColor(status);
  const icon = stageStatusIcon(status);
  return <Stack gap="xl" key={id}>
    {pageHeading}
    <Stack gap="sm"><Anchor component={Link} to="/app" size="sm" c="dimmed">К моим заявкам</Anchor>
      <Group gap="sm"><Text size="sm" c="dimmed">Заявка № {data.number}</Text><Badge color={color} c={`${color}.${status === 'current' ? 9 : 6}`} bg={`${color}.0`} variant="light" leftSection={<span aria-hidden="true">{icon === 'number' ? data.stage.index : icon}</span>}>{data.state === 'WITHDRAWN' ? 'Отозвана' : stateLabels[data.state]}</Badge></Group>
      <Title order={2} size="h2" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0 12px' }}><Text component="span" inherit c="dimmed">{products.data?.find((product) => product.code === data.product_code)?.name ?? 'Загружаем продукт…'} ·</Text><Text component="span" inherit fz={{ base: 28, sm: 40 }} c="gray.9">{formatMoney(data.offer?.amount ?? data.amount)}</Text><Text component="span" inherit c="dimmed">на {data.offer?.term_months ?? data.term_months} мес.</Text></Title>
    </Stack>
    <Paper withBorder p={{ base: 'md', sm: 'xl' }}><Stack gap="xl"><Timeline timeline={data.timeline} /><StatusPanel application={data} status={status} /></Stack></Paper>
    {message && <Notification role="alert" color="stop" withCloseButton={false}>{message}</Notification>}
    <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl" style={{ alignItems: 'start' }}>
      <Paper withBorder p={{ base: 'md', sm: 'xl' }}><Stack gap="lg"><Title order={2} size="h3">Параметры заявки</Title><KeyFigures application={data} calculation={calculation.data} error={calculation.isError} onRetry={() => void calculation.refetch()} /><Details application={data} company={companies.find(({ company }) => company.id === data.company_id)?.company} />
        {data.allowed_actions.includes('WITHDRAW') && <Anchor component="button" type="button" c="gray.9" ta="left" onClick={() => { setMessage(''); setConfirm(true); }}>Отозвать заявку</Anchor>}
      </Stack></Paper>
      <History timeline={data.timeline} />
    </SimpleGrid>
    {data.client_reason && <Stack gap="xs"><Text>{data.client_reason.text}</Text>{data.client_reason.action && <Text>{data.client_reason.action}</Text>}{data.client_reason.retry_after && <Text>Подать новую заявку можно с {new Date(data.client_reason.retry_after).toLocaleDateString('ru-RU', { timeZone: 'Europe/Moscow' })}</Text>}</Stack>}
    <section id="decision" /><section id="info-request" /><section id="submit" /><section id="signing" />
    <Modal opened={confirm} onClose={() => { if (!withdraw.isPending) setConfirm(false); }} title={`Отозвать заявку № ${data.number}? Это действие нельзя отменить.`} centered>
      <Group justify="flex-end"><Button variant="default" disabled={withdraw.isPending} onClick={() => setConfirm(false)}>Не отзывать</Button><Button loading={withdraw.isPending} onClick={() => withdraw.mutate()}>Отозвать</Button></Group>
    </Modal>
  </Stack>;
}
