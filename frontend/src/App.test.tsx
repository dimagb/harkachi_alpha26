import { MantineProvider } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, useLocation } from 'react-router';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import App from './App';
import { api } from './api/client';
import type { components } from './api/schema';
import { products } from './mocks/fixtures';

type Me = components['schemas']['MeResponse'];
const client: Me = {
  user: { id: 'client-1', full_name: 'Смирнова Анна Викторовна', role: 'CLIENT' },
  companies: [{ company: { id: 'company-1', inn: '770112345695', kind: 'IP', name: 'ИП Смирнова' }, position: 'Предприниматель', can_sign: true, is_founder: true }],
};
const bank: Me = { user: { id: 'bank-1', full_name: 'Орлова Мария Андреевна', role: 'UNDERWRITER' }, companies: [] };
const server = setupServer(
  http.post<never, components['schemas']['LoginRequest']>('*/api/v1/auth/login', async ({ request }) => {
    const { login } = await request.json();
    return HttpResponse.json({ access_token: login, token_type: 'bearer', expires_in: 3600, user: login === 'underwriter' ? bank.user : client.user });
  }),
  http.get('*/api/v1/me', ({ request }) => {
    const token = request.headers.get('Authorization');
    if (!token) return HttpResponse.json({ error: { code: 'UNAUTHORIZED', message: 'Войдите снова', details: {} } }, { status: 401 });
    return HttpResponse.json(token === 'Bearer underwriter' ? bank : client);
  }),
  http.get('*/api/v1/health', () => HttpResponse.json({ status: 'ok' })),
  http.get('*/api/v1/products', () => HttpResponse.json<components['schemas']['Product'][]>(products)),
  http.get('*/api/v1/applications', () => HttpResponse.json<components['schemas']['ApplicationListItem'][]>([])),
);

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
  notifications.clean();
  server.resetHandlers();
});

function Location() {
  return <output aria-label="Текущий маршрут">{useLocation().pathname}</output>;
}
function open(path = '/login') {
  render(<MantineProvider env="test"><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><App /><Location /></MemoryRouter></QueryClientProvider></MantineProvider>);
}
async function login(name: string) {
  fireEvent.change(await screen.findByLabelText(/^Логин/), { target: { value: name } });
  fireEvent.change(screen.getByLabelText(/^Пароль/), { target: { value: 'demo2026' } });
  fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
}

it.each([['ip_good', '/app', 'Мои заявки'], ['underwriter', '/bank/queue', 'Очередь']])('вход %s открывает главную по роли', async (name, path, title) => {
  open();
  await login(name);
  expect((await screen.findByRole('heading', { name: title })).textContent).toBe(title);
  expect(screen.getByLabelText('Текущий маршрут').textContent).toBe(path);
  expect(sessionStorage.getItem('access_token')).toBe(name);
  expect(localStorage.getItem('access_token')).toBeNull();
  expect(screen.getByText(name === 'underwriter' ? 'Орлова Мария Андреевна' : 'Смирнова Анна Викторовна')).toBeTruthy();
});

it('без токена перенаправляет /app на /login', async () => {
  open('/app');
  await screen.findByRole('heading', { name: 'Вход' });
  expect(screen.getByLabelText('Текущий маршрут').textContent).toBe('/login');
});

it.each([['ip_good', '/bank/journal', '/app', 'Мои заявки'], ['underwriter', '/app/applications/new', '/bank/queue', 'Очередь']])('не пускает %s на маршрут другой роли', async (token, path, home, title) => {
  sessionStorage.setItem('access_token', token);
  open(path);
  await screen.findByRole('heading', { name: title });
  expect(screen.getByLabelText('Текущий маршрут').textContent).toBe(home);
});

it.each([
  ['ip_good', '/app/applications/new', 'Зачем нужны деньги?'],
  ['ip_good', '/app/applications/123', 'Карточка заявки'],
  ['underwriter', '/bank/applications/123', 'Карточка андеррайтера'],
  ['underwriter', '/bank/journal', 'Журнал банка'],
])('восстанавливает сессию %s и открывает %s', async (token, path, title) => {
  sessionStorage.setItem('access_token', token);
  open(path);
  await screen.findByRole('heading', { name: title });
  expect(screen.getByLabelText('Текущий маршрут').textContent).toBe(path);
});

it('выход очищает токен и закрывает защищённый экран', async () => {
  sessionStorage.setItem('access_token', 'ip_good');
  open('/app');
  fireEvent.click(await screen.findByRole('button', { name: 'Выйти' }));
  await screen.findByRole('heading', { name: 'Вход' });
  expect(sessionStorage.getItem('access_token')).toBeNull();
  expect(screen.queryByText('ИП Смирнова')).toBeNull();
});

it('401 от любого API-запроса завершает сессию и возвращает на /login', async () => {
  sessionStorage.setItem('access_token', 'ip_good');
  open('/app');
  await screen.findByRole('heading', { name: 'Мои заявки' });
  server.use(http.get('*/api/v1/products', () => HttpResponse.json({ error: { code: 'UNAUTHORIZED', message: 'Сессия истекла', details: {} } }, { status: 401 })));
  await act(async () => { await api.GET('/products'); });
  await screen.findByRole('heading', { name: 'Вход' });
  expect(screen.getByLabelText('Текущий маршрут').textContent).toBe('/login');
  expect(sessionStorage.getItem('access_token')).toBeNull();
});

it('показывает ApiError уведомлением и ошибки полей в форме', async () => {
  server.use(http.post('*/api/v1/auth/login', () => HttpResponse.json({ error: { code: 'VALIDATION_ERROR', message: 'Проверьте данные для входа', details: { fields: { login: 'Неизвестный логин', password: 'Проверьте пароль' } } } }, { status: 422 })));
  open();
  await login('unknown');
  expect(await screen.findByText('Проверьте данные для входа')).toBeTruthy();
  expect(screen.getByText('Неизвестный логин')).toBeTruthy();
  expect(screen.getByText('Проверьте пароль')).toBeTruthy();
  expect(sessionStorage.getItem('access_token')).toBeNull();
});

it('оставляет возможность повторить загрузку профиля при временной ошибке', async () => {
  sessionStorage.setItem('access_token', 'ip_good');
  server.use(http.get('*/api/v1/me', () => HttpResponse.json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Попробуйте позже', details: {} } }, { status: 503 })));
  open('/app');
  await screen.findByText('Попробуйте позже');
  server.resetHandlers();
  fireEvent.click(await screen.findByRole('button', { name: 'Повторить' }));
  await screen.findByRole('heading', { name: 'Мои заявки' });
});

it('даёт выбрать компанию и перейти к новой заявке', async () => {
  sessionStorage.setItem('access_token', 'ip_good');
  const membership = client.companies[0]!;
  const requestedCompanies: string[] = [];
  server.use(http.get('*/api/v1/me', () => HttpResponse.json({ ...client, companies: [...client.companies, { ...membership, company: { ...membership.company, id: 'company-2', name: 'Вторая компания' } }] })));
  server.use(http.get('*/api/v1/applications', ({ request }) => {
    requestedCompanies.push(new URL(request.url).searchParams.get('company_id')!);
    return HttpResponse.json<components['schemas']['ApplicationListItem'][]>([]);
  }));
  open('/app');
  await screen.findByText('Заявок пока нет');
  const select = await screen.findByRole('combobox', { name: 'Компания' });
  fireEvent.click(select);
  fireEvent.click(await screen.findByRole('option', { name: 'Вторая компания' }));
  await waitFor(() => expect((select as HTMLInputElement).value).toBe('Вторая компания'));
  await waitFor(() => expect(requestedCompanies).toEqual(['company-1', 'company-2']));
  fireEvent.click(screen.getByRole('link', { name: 'Новая заявка' }));
  await screen.findByRole('heading', { name: 'Зачем нужны деньги?' });
  expect(screen.getByLabelText('Текущий маршрут').textContent).toBe('/app/applications/new');
  fireEvent.click(screen.getByRole('button', { name: 'Оборудование и развитие' }));
  await screen.findByRole('region', { name: 'Экспресс-кредит' });
  expect(screen.queryByRole('region', { name: 'Оборотный кредит' })).toBeNull();
});

it('запрашивает health с единственным префиксом API', async () => {
  const { data } = await api.GET('/health');
  expect(data).toEqual({ status: 'ok' });
});

it('не показывает ошибку соединения при отмене запроса', async () => {
  server.use(http.get('*/api/v1/products', async () => { await delay(50); return HttpResponse.json([]); }));
  open();
  await screen.findByRole('heading', { name: 'Вход' });
  const controller = new AbortController();
  await act(async () => {
    const pending = api.GET('/products', { signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
  expect(screen.queryByText('Нет связи с сервером. Проверьте соединение и попробуйте ещё раз.')).toBeNull();
});

