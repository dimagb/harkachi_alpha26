import { AppShell, Burger, Button, Container, Drawer, Group, Loader, Select, Stack, Text } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import css from './screens/application/Card.module.css';
import shell from './App.module.css';
import { Notifications } from '@mantine/notifications';
import { useQuery } from '@tanstack/react-query';
import { useState, useSyncExternalStore } from 'react';
import { Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router';
import { api } from './api/client';
import type { components } from './api/schema';
import { getToken, setToken, subscribeSession } from './auth/session';
import Login from './Login';
import { CompanyProvider, useCompany } from './company/CompanyContext';
import MyApplications from './screens/MyApplications';
import NewApplication from './screens/NewApplication';
import ApplicationCard from './screens/ApplicationCard';
import BankLayout from './screens/bank/BankLayout';
import Queue from './screens/bank/Queue';
import UnderwriterCard from './screens/bank/UnderwriterCard';
import Journal from './screens/bank/Journal';
import ProtocolPrint from './screens/bank/ProtocolPrint';

type Me = components['schemas']['MeResponse'];

function Shell({ me }: { me: Me }) {
  const { companyId, membership, setCompanyId } = useCompany();
  const home = me.user.role === 'UNDERWRITER' ? '/bank/queue' : '/app';
  const desktop = useMediaQuery('(min-width: 62em)');
  const { pathname } = useLocation();
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const opened = menuPath === pathname;
  const links = me.user.role === 'UNDERWRITER'
    ? (desktop ? [] : [['/bank/queue', 'Очередь'], ['/bank/journal', 'Журнал банка']])
    : [['/app', 'Мои заявки'], ['/app/applications/new', 'Получить финансирование']];
  const company = me.companies.length > 1
    ? <Select id="company" label="Компания" value={companyId ?? me.companies[0]?.company.id} onChange={setCompanyId} allowDeselect={false} data={me.companies.map(({ company }) => ({ value: company.id, label: company.name }))} />
    : membership && <span className={css.muted}>{membership.company.name}</span>;
  return <AppShell navbar={{ width: 240, breakpoint: 'md', collapsed: { mobile: true } }}>
    {desktop ? <AppShell.Navbar className={css.navbar} component="nav" aria-label="Главная навигация">
      <div className={css.navTop}><Link className={css.brand} to={home}>Кредитный кабинет</Link>{me.companies.length > 1 && company}<div className={css.navLinks}>{links.map(([to, label]) => <Link key={to} to={to!} className={css.navLink} aria-current={(to === '/app' ? pathname.startsWith('/app') && pathname !== '/app/applications/new' : pathname === to) ? 'page' : undefined}>{label}</Link>)}</div></div>
      <div className={css.navBottom}><span style={{ fontWeight: 500 }}>{me.user.full_name}</span><button type="button" className={css.textButton} style={{ alignSelf: 'flex-start', height: 'auto', fontSize: 'var(--mantine-font-size-sm)', fontWeight: 400 }} onClick={() => setToken(null)}>Выйти</button></div>
    </AppShell.Navbar> : null}
    <AppShell.Main>
      {!desktop && <>
        <header className={shell.mobileHeader}><Link className={shell.brand} to={home}>Кредитный кабинет</Link><Burger opened={opened} onClick={() => setMenuPath(opened ? null : pathname)} aria-label={opened ? 'Закрыть меню' : 'Открыть меню'} aria-expanded={opened} aria-controls="client-menu" /></header>
        <Drawer opened={opened} onClose={() => setMenuPath(null)} title="Меню кабинета" closeButtonProps={{ 'aria-label': 'Закрыть меню' }} position="right" size="100%">
          <div id="client-menu" className={shell.menu}>
            <nav className={css.navLinks} aria-label="Навигация кабинета">{links.map(([to, label]) => <Link key={to} to={to!} onClick={() => setMenuPath(null)} className={css.navLink} aria-current={pathname === to ? 'page' : undefined}>{label}</Link>)}</nav>
            {company}
            <div className={shell.identity}><Text fw={500}>{me.user.full_name}</Text><Button variant="default" onClick={() => setToken(null)}>Выйти</Button></div>
          </div>
        </Drawer>
      </>}
      <div className={css.shellMain}><Outlet /></div>
    </AppShell.Main>
  </AppShell>;
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
          <Route path="/app/applications/:id" element={client ? <ApplicationCard companies={me.data.companies} userId={me.data.user.id} /> : <Navigate to={home} replace />} />
        </Route>
        <Route element={underwriter ? <BankLayout me={me.data} /> : <Navigate to={home} replace />}>
          <Route path="/bank/queue" element={<Queue />} />
          <Route path="/bank/applications/:id" element={<UnderwriterCard />} />
          <Route path="/bank/journal" element={<Journal />} />
        </Route>
        <Route path="/bank/applications/:id/protocol" element={underwriter ? <ProtocolPrint /> : <Navigate to={home} replace />} />
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>
    );
  }

  return <><Notifications position="top-right" />{content}</>;
}

