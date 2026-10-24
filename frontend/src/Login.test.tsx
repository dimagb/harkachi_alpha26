import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { MantineProvider } from '@mantine/core';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import Login from './Login';
import { api } from './api/client';
import { accounts, applications, companyProfiles } from './mocks/fixtures';
import { createHandlers } from './mocks/handlers';

interface Persona {
  code: string;
  name: string;
  inn: string;
  ogrn: string;
  kind: string;
  users: { login: string; full_name: string; position: string; can_sign: boolean }[];
}

const contract = JSON.parse(readFileSync(resolve(process.cwd(), '../contracts/personas.json'), 'utf8')) as {
  staff: { login: string }[];
  personas: Persona[];
};
const logins = ['ip_good', 'ooo_load', 'ooo_load_accountant', 'ooo_gap', 'ip_bad', 'ooo_border', 'ooo_aml', 'underwriter'];
const server = setupServer(...createHandlers());

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  server.events.removeAllListeners();
  vi.unstubAllEnvs();
});
afterAll(() => server.close());

function renderLogin() {
  return render(<MantineProvider><Login /></MantineProvider>);
}

describe('Демо-учётки на входе', () => {
  it.each(['true', 'false'])('показывает все 8 учёток и общий пароль при VITE_USE_MSW=%s', (useMsw) => {
    vi.stubEnv('VITE_USE_MSW', useMsw);
    renderLogin();
    const list = screen.getByRole('list', { name: 'Демо-учётки' });
    const buttons = within(list).getAllByRole('button');
    expect(buttons).toHaveLength(8);
    expect(buttons.map((button) => button.querySelector('code')?.textContent)).toEqual(logins);
    const contractLogins = [...contract.staff, ...contract.personas.flatMap((persona) => persona.users)].map((user) => user.login);
    expect(new Set(buttons.map((button) => button.querySelector('code')?.textContent))).toEqual(new Set(contractLogins));
    expect(getComputedStyle(screen.getByText('Пароль для всех учёток: demo2026')).visibility).toBe('visible');
    expect(Boolean(screen.queryByText('Работа без сервера.'))).toBe(useMsw === 'true');
  });

  it('клик по ooo_border заполняет оба поля и переводит фокус на Войти без запроса входа', async () => {
    const requests: string[] = [];
    server.events.on('request:start', ({ request }) => {
      if (new URL(request.url).pathname.endsWith('/auth/login')) requests.push(request.url);
    });
    renderLogin();
    let submissions = 0;
    screen.getByRole('button', { name: 'Войти' }).closest('form')!.addEventListener('submit', () => { submissions += 1; });
    fireEvent.click(screen.getByRole('button', { name: /^ooo_border / }));
    expect((screen.getByLabelText(/^Логин/) as HTMLInputElement).value).toBe('ooo_border');
    expect((screen.getByLabelText(/^Пароль/, { selector: 'input' }) as HTMLInputElement).value).toBe('demo2026');
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Войти' }));
    await new Promise<void>((done) => setTimeout(done, 0));
    expect(submissions).toBe(0);
    expect(requests).toEqual([]);
  });

  it.each(logins)('MSW: вход %s с demo2026 возвращает 200', async (login) => {
    const { response, data } = await api.POST('/auth/login', { body: { login, password: 'demo2026' } });
    expect(response.status).toBe(200);
    expect(data?.access_token).toBeTruthy();
  });

  it.each(['ooo_gap', 'ooo_border'])('MSW: %s — директор из контракта с правом подписи и без заявок', (login) => {
    const persona = contract.personas.find((item) => item.code === login)!;
    const account = accounts[login];
    expect(account).toBeDefined();
    expect(account!.user).toMatchObject({ full_name: persona.users[0]!.full_name, role: 'CLIENT' });
    expect(account!.companies).toHaveLength(1);
    const membership = account!.companies[0]!;
    expect(membership).toMatchObject({ position: persona.users[0]!.position, can_sign: true, company: { name: persona.name, inn: persona.inn, kind: 'OOO' } });
    expect(companyProfiles[membership.company.id]).toMatchObject({ name: persona.name, inn: persona.inn, ogrn: persona.ogrn, kind: 'OOO' });
    expect(applications.filter((application) => application.company_id === membership.company.id)).toEqual([]);
  });

  it('MSW: ooo_aml показывает название компании из контракта', () => {
    const persona = contract.personas.find((item) => item.code === 'ooo_aml')!;
    expect(accounts.ooo_aml!.companies[0]!.company.name).toBe(persona.name);
  });
});
