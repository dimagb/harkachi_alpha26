import { readFileSync } from 'node:fs';
import { MantineProvider } from '@mantine/core';
import { Notifications, notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { createBankHandlers } from '../../mocks/bank/handlers';
import { products } from '../../mocks/fixtures';
import type { components } from '../../api/schema';
import { theme } from '../../theme';
import Queue from './Queue';
import UnderwriterCard from './UnderwriterCard';

const server = setupServer();
let queryClient: QueryClient;
beforeAll(() => {
  server.listen({ onUnhandledFrame: 'error' });
  Object.defineProperty(document, 'fonts', { configurable: true, value: { addEventListener: vi.fn(), removeEventListener: vi.fn() } });
});
afterAll(() => server.close());
beforeEach(() => {
  sessionStorage.setItem('access_token', 'demo:underwriter');
  server.resetHandlers(...createBankHandlers(), http.get('*/api/v1/products', () => HttpResponse.json(products)));
});
afterEach(() => { cleanup(); queryClient.clear(); sessionStorage.clear(); notifications.clean(); vi.useRealTimers(); });
function Location() { return <output aria-label="Маршрут">{useLocation().pathname}</output>; }
function open(id = 'ooo_border') {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<MantineProvider theme={theme} env="test"><QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[id === 'queue' ? '/bank/queue' : `/bank/applications/${id}`]}><Link to="/bank/queue">Открыть очередь</Link><Routes><Route path="/bank/queue" element={<Queue />} /><Route path="/bank/applications/:id" element={<UnderwriterCard />} /></Routes><Location /></MemoryRouter><Notifications /></QueryClientProvider></MantineProvider>);
}
async function ready(id = 'ooo_border') { open(id); await screen.findByRole('heading', { name: 'Факторы оценки' }); }
function choose(label: string) { fireEvent.click(screen.getByRole('radio', { name: label })); }
function comment(text = 'Первичные сведения проверены') { fireEvent.change(screen.getByLabelText('Комментарий (обязательно)'), { target: { value: text } }); }

it('показывает эталонные группы, итог, рекомендацию и платёж', async () => {
  await ready();
  const personas = JSON.parse(readFileSync('../contracts/personas.json', 'utf8'));
  const expected = personas.personas.find((p: { code: string }) => p.code === 'ooo_border').demo.expected.recommendation;
  const groups = [ ['Бизнес', ['business_age', 'industry_risk', 'mass_registration'], 20], ['Обороты', ['turnover_stability', 'turnover_trend', 'zero_months'], 30], ['Нагрузка', ['payment_to_turnover', 'debt_to_turnover'], 25], ['Кредитная история', ['delinquency_12m', 'credit_history_length', 'bureau_inquiries_30d'], 20], ['Дисциплина', ['payment_discipline'], 5] ] as const;
  for (const [name, codes, max] of groups) {
    const total = codes.reduce((sum, code) => sum + expected.points[code], 0);
    expect(within(screen.getByRole('group', { name })).getByText(`${total} / ${max}`)).toBeTruthy();
  }
  expect(screen.getByText(`Итого ${expected.score} / 100`)).toBeTruthy();
  expect(screen.getByText(`Класс ${expected.grade}`)).toBeTruthy();
  expect(screen.getByText('Одобрить 1 000 000 ₽ на 24 мес. под 26 %', { exact: false })).toBeTruthy();
  expect(screen.getByText(new RegExp(new Intl.NumberFormat('ru-RU').format(expected.offer.monthly_payment).replace(/\s/g, '\\s') + '\\s₽'))).toBeTruthy();
  expect(screen.queryByText(/порог B/)).toBeNull();
});

it('раскрывает БКИ под фактором и сворачивает повторным кликом', async () => {
  await ready();
  const factor = screen.getByRole('button', { name: /Платежи к поступлениям/ });
  fireEvent.click(factor);
  expect(factor.getAttribute('aria-expanded')).toBe('true');
  const source = await screen.findByRole('region', { name: 'Первоисточник: Платежи к поступлениям' });
  expect(within(source).getByText(/Платежи по кредитам в месяц — 150\s000\s₽/)).toBeTruthy();
  expect(within(source).getByText(/Получено 23.10 14:03/)).toBeTruthy();
  expect(within(source).getByText(/Средний оборот —/)).toBeTruthy();
  fireEvent.click(factor);
  expect(factor.getAttribute('aria-expanded')).toBe('false');
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Первоисточник: Платежи к поступлениям' })).toBeNull());
});

it('валидирует комментарий, встречное и максимум пяти вопросов', async () => {
  await ready();
  expect(screen.getByRole('button', { name: 'Принять решение' }).hasAttribute('disabled')).toBe(true);
  comment('мало');
  expect(screen.getByRole('button', { name: 'Принять решение' }).hasAttribute('disabled')).toBe(true);
  comment();
  expect(screen.getByRole('button', { name: 'Принять решение' }).hasAttribute('disabled')).toBe(false);
  choose('Встречное');
  expect(screen.getByRole('button', { name: 'Принять решение' }).hasAttribute('disabled')).toBe(true);
  expect(screen.getByText('Встречное предложение должно отличаться от заявки по сумме или сроку')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '800000' } });
  expect(screen.getByText(/Решение не совпадает с рекомендацией/)).toBeTruthy();
  choose('Запросить данные');
  for (let i = 0; i < 4; i++) fireEvent.click(screen.getByRole('button', { name: 'Добавить вопрос' }));
  expect(screen.getAllByLabelText(/^Вопрос \d/)).toHaveLength(5);
  expect(screen.getByRole('button', { name: 'Добавить вопрос' }).hasAttribute('disabled')).toBe(true);
  expect(screen.getByRole('button', { name: 'Принять решение' }).hasAttribute('disabled')).toBe(true);
  screen.getAllByLabelText(/^Вопрос \d/).forEach(input => fireEvent.change(input, { target: { value: 'Подтвердите обороты за месяц' } }));
  expect(screen.getByRole('button', { name: 'Принять решение' }).hasAttribute('disabled')).toBe(false);
});

it('отправляет только поля одобрения, обновляет экран и очередь', async () => {
  let submitted: unknown;
  server.events.on('request:start', async ({ request }) => { if (request.method === 'POST') submitted = await request.clone().json(); });
  await ready(); comment();
  fireEvent.click(screen.getByRole('button', { name: 'Принять решение' }));
  await screen.findByRole('heading', { name: 'Решение принято' });
  expect(submitted).toEqual({ outcome: 'APPROVE', amount: 1000000, term_months: 24, comment: 'Первичные сведения проверены' });
  expect(screen.queryByLabelText('Комментарий (обязательно)')).toBeNull();
  fireEvent.click(screen.getByRole('link', { name: 'Вернуться в очередь' }));
  await screen.findByRole('heading', { name: 'Очередь' });
  await screen.findByText('Источник данных недоступен');
  expect(screen.queryByText('ООО «ТехноМонтаж»')).toBeNull();
});

it('показывает 409 и перезагружает карточку', async () => {
  server.use(http.post('*/api/v1/underwriting/:id/decision', () => HttpResponse.json({ error: { code: 'INVALID_TRANSITION', message: 'Уже решено', details: {} } }, { status: 409 })));
  await ready(); comment();
  fireEvent.click(screen.getByRole('button', { name: 'Принять решение' }));
  expect(await screen.findByText('Заявка уже не на рассмотрении')).toBeTruthy();
});

it('показывает ошибки сервера под полями', async () => {
  server.use(http.post('*/api/v1/underwriting/:id/decision', () => HttpResponse.json({ error: { code: 'VALIDATION_ERROR', message: 'Проверьте поля', details: { fields: { comment: 'Уточните обоснование' } } } }, { status: 422 })));
  await ready(); comment();
  fireEvent.click(screen.getByRole('button', { name: 'Принять решение' }));
  expect(await screen.findByText('Уточните обоснование')).toBeTruthy();
});

it('даёт повторить сбор только для SOURCE_UNAVAILABLE', async () => {
  await ready('source_unavailable');
  expect(screen.getByRole('radio', { name: 'Повторить сбор сведений' })).toBeTruthy();
  expect(screen.getByText('Не ответил (3 попытки)')).toBeTruthy();
  choose('Повторить сбор сведений'); comment();
  fireEvent.click(screen.getByRole('button', { name: 'Принять решение' }));
  await screen.findByRole('heading', { name: 'Решение принято' });
});

it('показывает AML, внутренний стоп-фактор и скрывает форму', async () => {
  open('ooo_aml');
  await screen.findByText('Признаки AML');
  expect(screen.getByText('SF_ADDITIONAL')).toBeTruthy();
  expect(screen.getByText('Стоп-фактор')).toBeTruthy();
  expect(screen.queryByLabelText('Комментарий (обязательно)')).toBeNull();
});

it('показывает очередь в серверном порядке с ожиданием, переходит в карточку', async () => {
  vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date('2026-10-23T11:15:00Z'));
  open('queue');
  const row = (await screen.findByText('ООО «ТехноМонтаж»')).closest('tr')!;
  expect(within(row).getByText('Пограничная оценка')).toBeTruthy();
  expect(within(row).getByText('12 мин')).toBeTruthy();
  fireEvent.click(within(row).getByRole('link'));
  await screen.findByRole('heading', { name: 'Факторы оценки' });
  expect(screen.getByLabelText('Маршрут').textContent).toBe('/bank/applications/ooo_border');
  expect(screen.queryByRole('radio', { name: 'Повторить сбор сведений' })).toBeNull();
});

it('обновляет очередь через 10 секунд и показывает пустое состояние', async () => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
  open('queue'); await screen.findByText('ООО «ТехноМонтаж»');
  server.use(http.get('*/api/v1/underwriting/queue', () => HttpResponse.json([])));
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  vi.useRealTimers();
  expect(await screen.findByText('Очередь пуста. Новые заявки появятся здесь автоматически')).toBeTruthy();
});

it('чтение истории показывает только события API', async () => {
  await ready();
  fireEvent.click(screen.getByRole('tab', { name: 'История заявки' }));
  expect(screen.getByText('Решение принято системой')).toBeTruthy();
  expect(screen.queryByText('Заявка взята в работу')).toBeNull();
});

it('продолжает опрос в ENRICHMENT и останавливает в MANUAL_REVIEW', async () => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
  let reads = 0;
  const response = await fetch('http://localhost/api/v1/underwriting/applications/ooo_border', { headers: { Authorization: 'Bearer demo:underwriter' } });
  const fixture: components['schemas']['ApplicationBank'] = await response.json();
  server.use(http.get('*/api/v1/underwriting/applications/ooo_border', () => { reads++; return HttpResponse.json({ ...fixture, state: reads === 1 ? 'ENRICHMENT' : 'MANUAL_REVIEW' }); }));
  await ready();
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  await screen.findByLabelText('Комментарий (обязательно)');
  const count = reads;
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); }); vi.useRealTimers();
  expect(reads).toBe(count);
});
