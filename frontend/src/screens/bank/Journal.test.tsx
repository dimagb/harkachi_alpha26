import { MantineProvider } from '@mantine/core';
import { Notifications, notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router';
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { createBankHandlers } from '../../mocks/bank/handlers';
import { createJournalHandlers } from '../../mocks/bank/journal';
import { bankApplications } from '../../mocks/bank/fixtures';
import { theme } from '../../theme';
import Journal from './Journal';

const server = setupServer();
let client: QueryClient;
beforeAll(() => { server.listen({ onUnhandledFrame: 'error' }); Object.defineProperty(document, 'fonts', { configurable: true, value: { addEventListener: vi.fn(), removeEventListener: vi.fn() } }); });
afterAll(() => server.close());
beforeEach(() => { sessionStorage.setItem('access_token', 'demo:underwriter'); server.resetHandlers(...createJournalHandlers(), ...createBankHandlers()); });
afterEach(() => { cleanup(); client.clear(); notifications.clean(); sessionStorage.clear(); server.events.removeAllListeners(); });
function open() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<MantineProvider theme={theme} env="test"><QueryClientProvider client={client}><MemoryRouter><Journal /></MemoryRouter><Notifications /></QueryClientProvider></MantineProvider>);
}
async function ready() { open(); await screen.findByText('Показано 1–20 из 28'); }
function filter(name: string) { fireEvent.click(screen.getByRole('combobox', { name: 'Этап' })); fireEvent.click(screen.getByRole('option', { name })); }

it('показывает 20 строк, московское время, страницу 2 и сбрасывает страницу фильтром', async () => {
  const urls: URL[] = [];
  server.events.on('request:start', ({ request }) => { if (request.url.includes('/bank/applications')) urls.push(new URL(request.url)); });
  await ready();
  expect(within(screen.getByRole('table', { name: 'Заявки банка' })).getAllByRole('row')).toHaveLength(21);
  expect(screen.getAllByText('23.10 14:03').length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('button', { name: 'Страница 2' }));
  await screen.findByText('Показано 21–28 из 28');
  expect(urls.at(-1)?.searchParams.get('page')).toBe('2');
  filter('Рассмотрение специалистом');
  await screen.findByText('Показано 1–6 из 6');
  expect(urls.at(-1)?.searchParams.get('state')).toBe('MANUAL_REVIEW');
  expect(urls.at(-1)?.searchParams.get('page')).toBe('1');
  const rows = within(screen.getByRole('table', { name: 'Заявки банка' })).getAllByRole('row').slice(1);
  expect(rows.every(row => within(row).queryByText('Рассмотрение специалистом'))).toBe(true);
  filter('Все'); await screen.findByText('Показано 1–20 из 28');
  expect(urls.at(-1)?.searchParams.has('state')).toBe(false);
});

it('раскрывает события и ссылки, сохраняет русский текст примечания', async () => {
  await ready();
  fireEvent.click(screen.getByRole('button', { name: 'События заявки № 1047' }));
  expect(await screen.findByText('Оценка 54 из 100, класс C')).toBeTruthy();
  expect(screen.getByText('Решение принято')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Открыть карточку' }).getAttribute('href')).toBe('/bank/applications/ooo_border');
  const print = screen.getByRole('link', { name: 'Печать протокола' });
  expect(print.getAttribute('href')).toBe('/bank/applications/ooo_border/protocol');
  expect(print.getAttribute('target')).toBe('_blank');
});

it('кнопка демо есть только у оферты, подписания и дозапроса', async () => {
  await ready();
  for (const row of within(screen.getByRole('table', { name: 'Заявки банка' })).getAllByRole('row').slice(1)) {
    const eligible = /Предложение выдано|Подписание|Запрошены данные/.test(row.textContent ?? '');
    expect(!!within(row).queryByRole('button', { name: /Перемотать время/ })).toBe(eligible);
  }
});

it.each([0, 401])('не отправляет %i дней и показывает ошибку', async days => {
  let posts = 0; server.events.on('request:start', ({ request }) => { if (request.method === 'POST') posts++; });
  await ready(); fireEvent.click(screen.getAllByRole('button', { name: /Перемотать время/ })[0]!);
  const dialog = await screen.findByRole('dialog');
  fireEvent.change(within(dialog).getByLabelText('Дней'), { target: { value: String(days) } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Перемотать' }));
  expect(await within(dialog).findByText('Введите целое число от 1 до 400')).toBeTruthy();
  expect(posts).toBe(0);
});

it('отправляет точное тело, обновляет строку и раскрытые события после истечения', async () => {
  let body: unknown;
  server.events.on('request:start', async ({ request }) => { if (request.method === 'POST') body = await request.clone().json(); });
  await ready();
  const row = screen.getAllByRole('button', { name: /Перемотать время/ })[0]!.closest('tr')!;
  const number = within(row).getByRole('button', { name: /События заявки/ });
  fireEvent.click(number); await screen.findByRole('link', { name: 'Открыть карточку' });
  const id = screen.getByRole('link', { name: 'Открыть карточку' }).getAttribute('href')!.split('/').at(-1);
  fireEvent.click(within(row).getByRole('button', { name: /Перемотать время/ }));
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Перемотать' }));
  expect(await screen.findByText('Срок истёк — заявка закрыта')).toBeTruthy();
  expect(body).toEqual({ application_id: id, days: 31 });
  await waitFor(() => expect(within(number.closest('tr')!).getByText('Срок истёк')).toBeTruthy());
  expect(await screen.findByText('Срок истёк после перемотки времени')).toBeTruthy();
});

it.each([403, 404])('объясняет отключённый демо-режим при %i', async status => {
  server.use(http.post('*/api/v1/demo/time-shift', () => HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Нет', details: {} } }, { status })));
  await ready(); fireEvent.click(screen.getAllByRole('button', { name: /Перемотать время/ })[0]!);
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Перемотать' }));
  expect(await screen.findByText('Демо-режим выключен на сервере')).toBeTruthy();
});

it('показывает пустой результат и повторяет загрузку после ошибки', async () => {
  server.use(http.get('*/api/v1/bank/applications', () => HttpResponse.json({ error: { code: 'INTERNAL_ERROR', message: 'Не удалось загрузить журнал', details: {} } }, { status: 500 })));
  open(); await screen.findByRole('button', { name: 'Повторить' });
  server.use(http.get('*/api/v1/bank/applications', () => HttpResponse.json({ items: [], page: 1, size: 20, total: 0 })));
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
  expect(await screen.findByText('Заявок с таким состоянием нет')).toBeTruthy();
});

it('возвращается на существующую страницу, если последняя оферта на странице истекла', async () => {
  let total = 21;
  server.use(
    http.get('*/api/v1/bank/applications', ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get('page') ?? 1);
      const source = bankApplications[0]!;
      const all = Array.from({ length: total }, (_, i) => ({ id: `last-${i}`, number: 2000 + i, company_name: `Компания ${i}`, company_kind: 'OOO', product_code: 'EXPRESS', amount: 1000000, grade: 'A', route_reason: 'GRADE_C', waiting_since: source.updated_at, updated_at: source.updated_at, state: 'OFFER_ISSUED' }));
      return HttpResponse.json({ items: all.slice((page - 1) * 20, page * 20), total, page, size: 20 });
    }),
    http.post('*/api/v1/demo/time-shift', () => { total = 20; return HttpResponse.json({ application_id: 'last-20', expired_now: true, state: 'EXPIRED' }); }),
  );
  open(); await screen.findByText('Показано 1–20 из 21');
  fireEvent.click(screen.getByRole('button', { name: 'Страница 2' }));
  await screen.findByText('Показано 21–21 из 21');
  fireEvent.click(screen.getByRole('button', { name: /Перемотать время/ }));
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Перемотать' }));
  expect(await screen.findByText('Показано 1–20 из 20')).toBeTruthy();
  expect(screen.queryByText('Заявок с таким состоянием нет')).toBeNull();
});
