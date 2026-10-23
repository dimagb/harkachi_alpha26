import { Anchor, Button, Container, Group, Loader, Paper, Select, Stack, Text, Title } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { useQuery } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { Link, Navigate, Outlet, Route, Routes } from 'react-router';
import { api } from './api/client';
import type { components } from './api/schema';
import { getToken, setToken, subscribeSession } from './auth/session';
import Login from './Login';
import { CompanyProvider, useCompany } from './company/CompanyContext';
import MyApplications from './screens/MyApplications';
import NewApplication from './screens/NewApplication';

// TODO(lead): обновить App.test.tsx: вместо заглушки «Заявка» теперь подбор;
// тестам маршрутов нужны обработчики /products и /applications (файл вне F-03).

type Me = components['schemas']['MeResponse'];

function Shell({ me }: { me: Me }) {
  const { companyId, membership, setCompanyId } = useCompany();
  const home = me.user.role === 'UNDERWRITER' ? '/bank/queue' : '/app';
  return (
    <>
      <Paper component="header" withBorder radius={0} p="md">
        <Group justify="space-between" wrap="wrap">
          <Anchor component={Link} to={home} c="red" fw={700}>Кредитный кабинет</Anchor>
          <Group>
            <Text size="sm">{me.user.full_name}</Text>
            {me.companies.length === 1 && <Text size="sm" c="dimmed">{membership?.company.name}</Text>}
            {me.companies.length > 1 && <Select id="company" label="Компания" value={companyId ?? me.companies[0]?.company.id} onChange={setCompanyId} allowDeselect={false} data={me.companies.map(({ company }) => ({ value: company.id, label: company.name }))} />}
            {me.user.role === 'CLIENT' && <Anchor component={Link} to="/app/applications/new">Новая заявка</Anchor>}
            {me.user.role === 'UNDERWRITER' && <><Anchor component={Link} to="/bank/queue">Очередь</Anchor><Anchor component={Link} to="/bank/journal">Журнал банка</Anchor></>}
            <Button variant="default" onClick={() => setToken(null)}>Выйти</Button>
          </Group>
        </Group>
      </Paper>
      <Container component="main" size="lg" py="xl"><Outlet /></Container>
    </>
  );
}

export default function App() {
  const token = useSyncExternalStore(subscribeSession, getToken);
  const me = useQuery({
    queryKey: ['me', token],
    queryFn: async ({ signal }) => {
      const { data, error } = await api.GET('/me', { signal });
      if (error || !data) throw new Error('Не удалось загрузить профиль.');
      return data;
    },
    enabled: !!token,
    retry: false,
    gcTime: 0,
  });
  const home = me.data?.user.role === 'UNDERWRITER' ? '/bank/queue' : '/app';
  const client = me.data?.user.role === 'CLIENT';
  const underwriter = me.data?.user.role === 'UNDERWRITER';

  let content;
  if (!token) {
    content = <Routes><Route path="/login" element={<Login />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes>;
  } else if (me.isPending) {
    content = <Container py="xl"><Group role="status"><Loader size="sm" /><Text>Загружаем профиль…</Text></Group></Container>;
  } else if (me.isError || !me.data) {
    content = <Container py="xl"><Stack align="flex-start"><Text>Не удалось загрузить профиль.</Text><Button onClick={() => void me.refetch()}>Повторить</Button><Button variant="default" onClick={() => setToken(null)}>Выйти</Button></Stack></Container>;
  } else if (!client && !underwriter) {
    content = <Container py="xl"><Text>Для этой учётной записи кабинет пока недоступен.</Text><Button onClick={() => setToken(null)}>Выйти</Button></Container>;
  } else {
    content = (
      <Routes>
        <Route element={<CompanyProvider key={me.data.user.id} companies={me.data.companies}><Shell me={me.data} /></CompanyProvider>}>
          <Route path="/app" element={client ? <MyApplications /> : <Navigate to={home} replace />} />
          <Route path="/app/applications/new" element={client ? <NewApplication /> : <Navigate to={home} replace />} />
          <Route path="/app/applications/:id" element={client ? <Title order={1}>Карточка заявки</Title> : <Navigate to={home} replace />} />
          <Route path="/bank/queue" element={underwriter ? <Title order={1}>Очередь</Title> : <Navigate to={home} replace />} />
          <Route path="/bank/applications/:id" element={underwriter ? <Title order={1}>Карточка андеррайтера</Title> : <Navigate to={home} replace />} />
          <Route path="/bank/journal" element={underwriter ? <Title order={1}>Журнал банка</Title> : <Navigate to={home} replace />} />
        </Route>
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>
    );
  }

  return <><Notifications position="top-right" />{content}</>;
}

