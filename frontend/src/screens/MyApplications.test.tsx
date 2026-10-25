import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router';
import { afterAll, afterEach, beforeAll, beforeEach, expect, it } from 'vitest';
import App from '../App';
import { setToken } from '../auth/session';
import { accounts, applications } from '../mocks/fixtures';
import { createHandlers } from '../mocks/handlers';
import { theme } from '../theme';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => server.resetHandlers(...createHandlers()));
afterAll(() => server.close());
afterEach(() => { cleanup(); setToken(null); });

function open(login = 'ip_good') {
  setToken(`demo:${login}`);
  render(<MantineProvider theme={theme} env="test"><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/app']}><App /></MemoryRouter></QueryClientProvider></MantineProvider>);
}

it('показывает пустой список ip_good и открывает подбор', async () => {
  server.use(http.get('*/api/v1/applications', () => HttpResponse.json([])));
  open();
  expect(await screen.findByText('Заявок пока нет')).toBeTruthy();
  fireEvent.click(screen.getByRole('link', { name: 'Получить финансирование' }));
  expect(await screen.findByRole('heading', { name: 'Зачем нужны деньги?' })).toBeTruthy();
});

it('показывает номер, продукт, сумму, этап, дату и открывает карточку', async () => {
  open('ooo_load');
  const link = await screen.findByRole('link', { name: /№ 1002/ });
  expect(link.textContent).toContain('Оборотный кредит');
  expect(link.textContent?.replace(/\s/g, ' ')).toContain('4 000 000 ₽');
  expect(link.textContent).toContain('Решение');
  expect(link.textContent).toContain('23.10.2026');
  fireEvent.click(link);
  expect(await screen.findByRole('heading', { name: 'Карточка заявки' })).toBeTruthy();
});

it('выделяет заявку, которая ждёт подписи директора', async () => {
  server.use(http.get('*/api/v1/applications', () => HttpResponse.json([{ ...applications[1], awaiting_signature: true }])));
  open('ooo_load');
  expect(await screen.findByText('Ждёт подписи директора')).toBeTruthy();
});

it('сортирует заявки по последнему изменению, новые сверху', async () => {
  server.use(http.get('*/api/v1/applications', () => HttpResponse.json([
    { ...applications[1], id: 'old', number: 9901, updated_at: '2026-10-23T23:00:00Z' },
    { ...applications[1], id: 'new', number: 9902, updated_at: '2026-10-25T00:00:00Z' },
    { ...applications[1], id: 'middle', number: 9903, updated_at: '2026-10-24T12:00:00Z' },
  ])));
  open('ooo_load');
  await screen.findByRole('link', { name: /№ 9901/ });
  expect(screen.getAllByRole('link', { name: /№ 990/ }).map(link => link.getAttribute('href'))).toEqual([
    '/app/applications/new', '/app/applications/middle', '/app/applications/old',
  ]);
});

it.each(['INFO_REQUESTED', 'OFFER_ISSUED', 'SIGNING', 'DRAFT'] as const)('отмечает необходимое действие подписанта в %s', async state => {
  server.use(http.get('*/api/v1/applications', () => HttpResponse.json([{ ...applications[1], state, awaiting_signature: state === 'DRAFT' }])));
  open('ooo_load');
  const link = await screen.findByRole('link', { name: /№ 1002/ });
  expect(within(link).getByText('Нужно ваше действие')).toBeTruthy();
});

it.each(['ip_good', 'ooo_load_accountant'])('%s: не требует подписи от неподходящего пользователя или обычного черновика', async login => {
  server.use(http.get('*/api/v1/applications', () => HttpResponse.json([{ ...applications[login === 'ip_good' ? 0 : 1], state: 'DRAFT', awaiting_signature: login === 'ooo_load_accountant' }])));
  open(login);
  await screen.findByRole('link', { name: /№ 100/ });
  expect(screen.queryByText('Нужно ваше действие')).toBeNull();
});

it('смена компании в шапке загружает её заявки', async () => {
  const requested: string[] = [];
  server.use(
    http.get('*/api/v1/me', () => HttpResponse.json({ ...accounts.ooo_load, companies: [...accounts.ooo_load!.companies, ...accounts.ip_good!.companies] })),
    http.get('*/api/v1/applications', ({ request }) => {
      const id = new URL(request.url).searchParams.get('company_id')!;
      requested.push(id);
      return HttpResponse.json(applications.filter((item) => item.company_id === id));
    }),
  );
  open('ooo_load');
  expect(await screen.findByRole('link', { name: /№ 1002/ })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
  fireEvent.click(screen.getByRole('combobox', { name: 'Компания' }));
  fireEvent.click(await screen.findByRole('option', { name: 'ИП Смирнова Анна Викторовна' }));
  expect(await screen.findByRole('link', { name: /№ 1001/ })).toBeTruthy();
  await waitFor(() => expect(screen.queryByRole('link', { name: /№ 1002/ })).toBeNull());
  expect(requested).toEqual(['20000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000001']);
});

it('показывает ошибку списка и повторяет запрос', async () => {
  server.use(http.get('*/api/v1/applications', () => HttpResponse.json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Сервис временно недоступен.', details: {} } }, { status: 503 })));
  open();
  expect(await screen.findByText('Не удалось загрузить заявки. Попробуйте ещё раз.')).toBeTruthy();
  server.use(http.get('*/api/v1/applications', () => HttpResponse.json([])));
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
  expect(await screen.findByText('Заявок пока нет')).toBeTruthy();
});
