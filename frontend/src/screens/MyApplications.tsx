import { Badge, Button, Group, Loader, Stack, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { api } from '../api/client';
import { useCompany } from '../company/CompanyContext';
import { stateLabels } from '../ui/labels';
import { formatMoney, stageStatusColor } from '../ui/status';
import card from './application/Card.module.css';
import css from './MyApplications.module.css';

export default function MyApplications() {
  const { companyId, membership } = useCompany();
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
  return <div className={card.page}>
    <header className={card.header}><h1 className={css.heading}>Мои заявки</h1><Text c="dimmed">Следите за рассмотрением и отвечайте на запросы банка.</Text></header>
    {!companyId ? <div className={card.card}><Text>Для вашей учётной записи пока нет компании.</Text></div> : failed ? <div className={card.card}>
      <Text role="alert">Не удалось загрузить заявки. Попробуйте ещё раз.</Text>
      <Button variant="default" w="fit-content" onClick={() => { void products.refetch(); void applications.refetch(); }}>Повторить</Button>
    </div> : products.isPending || applications.isPending ? <div className={card.card}><Group role="status"><Loader size="sm" /><Text>Загружаем заявки…</Text></Group></div> : <>
      {!applications.data.length ? <div className={card.card}><Text fw={600}>Заявок пока нет</Text><Text c="dimmed">Выберите цель и узнайте, какие условия подойдут вашему бизнесу.</Text></div> :
        <Stack gap="md">{[...applications.data].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)).map((item) => <Link to={`/app/applications/${item.id}`} key={item.id} className={`${card.card} ${css.application}`}>
          <Stack gap="sm">
            {(['INFO_REQUESTED', 'OFFER_ISSUED', 'SIGNING'].includes(item.state) || item.state === 'DRAFT' && item.awaiting_signature && membership?.can_sign) && <Badge bg="var(--cc-wait-bg)" c="var(--cc-wait-text)" bd="1px solid var(--cc-wait-border)" style={{ whiteSpace: 'normal', height: 'auto', minHeight: 28 }}>Нужно ваше действие</Badge>}
            <Group justify="space-between"><Text fw={600}>№ {item.number} · {products.data.find(({ code }) => code === item.product_code)?.name}</Text><Text fw={700}>{formatMoney(item.amount)}</Text></Group>
            <Group justify="space-between"><Group gap="xs"><Badge color={stageStatusColor('current')} variant="light">{item.stage.title}</Badge>{stateLabels[item.state] !== 'Нужно ваше действие' && <Text size="sm" c="var(--mantine-color-text)">{stateLabels[item.state]}</Text>}{item.awaiting_signature && <Badge color={stageStatusColor('action_required')} variant="light">Ждёт подписи директора</Badge>}</Group><Text size="sm" c="var(--mantine-color-text)">{new Date(item.updated_at).toLocaleDateString('ru-RU', { timeZone: 'UTC' })}</Text></Group>
          </Stack>
        </Link>)}</Stack>}
      <Button component={Link} to="/app/applications/new" className={card.cta} w="fit-content" maw="100%">Получить финансирование</Button>
    </>}
  </div>;
}
