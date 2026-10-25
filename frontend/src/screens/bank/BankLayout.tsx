import { Burger, Button, Collapse } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router';
import { api } from '../../api/client';
import type { components } from '../../api/schema';
import { setToken } from '../../auth/session';
import css from './Bank.module.css';
import shell from '../../App.module.css';
import alfaLogo from '../../assets/alfa-logo.svg';
import PrototypeFooter from '../../PrototypeFooter';
// Та же видимая область официального SVG, что и в клиентской шапке.
const alfaLogoView = `${alfaLogo}#svgView(viewBox(152,97,189,288))`;

export function useBankQueue() {
  return useQuery({ queryKey: ['bank', 'queue'], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/underwriting/queue', { signal });
    if (error || !data) throw new Error(error?.error.message ?? 'Не удалось загрузить очередь');
    return data;
  }, refetchInterval: 10000 });
}

export default function BankLayout({ me }: { me: components['schemas']['MeResponse'] }) {
  const queue = useBankQueue();
  const { pathname } = useLocation();
  const [opened, setOpened] = useState(false);
  const navigation = <><Link aria-current={pathname !== '/bank/journal' ? 'page' : undefined} to="/bank/queue" onClick={() => setOpened(false)}>Очередь · {queue.isError ? 'недоступна' : queue.data?.length ?? '…'}</Link><Link aria-current={pathname === '/bank/journal' ? 'page' : undefined} to="/bank/journal" onClick={() => setOpened(false)}>Журнал банка</Link></>;
  return <div className={css.bank}>
    <header className={css.topbar}><div className={css.topLeft}><Link className={`${css.brand} ${shell.brand}`} to="/bank/queue"><img className={shell.logo} src={alfaLogoView} alt="Альфа-Банк" /><span>Кредитный конвейер</span></Link><nav className={css.desktopNav} aria-label="Навигация банка">{navigation}</nav></div><div className={css.identity}><span>Андеррайтер · {me.user.full_name}</span><Button variant="subtle" color="gray" size="compact-sm" onClick={() => setToken(null)}>Выйти</Button></div><Burger className={css.burger} opened={opened} onClick={() => setOpened(v => !v)} aria-label="Меню банка" aria-expanded={opened} /></header>
    <Collapse expanded={opened} className={css.mobileMenu}>{opened && <nav aria-label="Мобильная навигация банка">{navigation}<span>Андеррайтер · {me.user.full_name}</span><Button variant="default" onClick={() => setToken(null)}>Выйти</Button></nav>}</Collapse>
    <main className={css.main}><Outlet /></main>
    <PrototypeFooter />
  </div>;
}
