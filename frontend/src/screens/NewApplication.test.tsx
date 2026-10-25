import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, useLocation } from 'react-router';
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import type { components } from '../api/schema';
import { setToken } from '../auth/session';
import { createHandlers } from '../mocks/handlers';
import { products } from '../mocks/fixtures';
import { theme } from '../theme';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => server.resetHandlers(...createHandlers()));
afterAll(() => server.close());
afterEach(() => { cleanup(); setToken(null); vi.useRealTimers(); server.events.removeAllListeners(); });

function Location() { return <span data-testid="location">{useLocation().pathname}</span>; }

function open(login = 'ip_good') {
  setToken(`demo:${login}`);
  render(<MantineProvider theme={theme} env="test"><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/app/applications/new']}><App /><Location /></MemoryRouter></QueryClientProvider></MantineProvider>);
}
async function choose(purpose = 'Кассовый разрыв', product = 'Экспресс-кредит') {
  fireEvent.click(await screen.findByRole('button', { name: purpose }));
  fireEvent.click(within(await screen.findByRole('region', { name: product })).getByRole('button', { name: 'Выбрать' }));
  await screen.findByRole('heading', { name: 'Профиль компании' });
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Создать заявку' }).disabled).toBe(false));
}
function revenue() { fireEvent.change(screen.getByLabelText('Выручка за год, ₽'), { target: { value: '12000000' } }); }

// Изоляция сохранённых форм между тестами, включая существующие сценарии.
afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks(); });

it('оборудование предлагает только экспресс, кассовый разрыв — три продукта', async () => {
  open();
  fireEvent.click(await screen.findByRole('button', { name: 'Оборудование и развитие' }));
  expect(await screen.findByRole('region', { name: 'Экспресс-кредит' })).toBeTruthy();
  expect(screen.queryByRole('region', { name: 'Оборотный кредит' })).toBeNull();
  expect(screen.queryByRole('region', { name: 'Овердрафт' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Кассовый разрыв' }));
  expect(await screen.findByRole('region', { name: 'Оборотный кредит' })).toBeTruthy();
  expect(screen.getByRole('region', { name: 'Овердрафт' })).toBeTruthy();
});

it.each([['ooo_load', true], ['ip_good', false]] as const)('поручительство показывается только ООО: %s', async (login, needsGuarantee) => {
  open(login);
  fireEvent.click(await screen.findByRole('button', { name: 'Оборудование и развитие' }));
  await screen.findByRole('region', { name: 'Экспресс-кредит' });
  expect(!!screen.queryByText('Нужно поручительство владельца')).toBe(needsGuarantee);
  expect(screen.getByText(/ключевая ставка ЦБ 14[,.]00% на 23.10.2026/)).toBeTruthy();
});

it('овердрафт блокирует срок на 12 месяцах и показывает проценты за дни', async () => {
  open();
  await choose('Кассовый разрыв', 'Овердрафт');
  const term = screen.getByRole<HTMLInputElement>('radio', { name: '12' });
  expect(term.disabled).toBe(true);
  expect(term.checked).toBe(true);
  expect(await screen.findByText('Проценты — только за использованные дни')).toBeTruthy();
});

it('короткий набор сроков выбирается таблетками и отправляет выбранный срок', async () => {
  const express = products.find(product => product.code === 'EXPRESS')!;
  server.use(http.get('*/api/v1/products', () => HttpResponse.json([{ ...express, min_term_months: 6, max_term_months: 11 }])));
  let body: components['schemas']['ApplicationCreate'] | undefined;
  server.events.on('request:start', async ({ request }) => {
    if (request.url.endsWith('/applications') && request.method === 'POST') body = await request.clone().json();
  });
  open(); await choose();
  const terms = screen.getByRole('group', { name: 'Срок, мес.' });
  expect(within(terms).getAllByRole('radio')).toHaveLength(6);
  fireEvent.click(within(terms).getByRole('radio', { name: '11' }));
  expect(within(terms).getByRole<HTMLInputElement>('radio', { name: '11' }).checked).toBe(true);
  revenue();
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  await screen.findByRole('heading', { name: 'Карточка заявки' });
  expect(body?.term_months).toBe(11);
});

it('больше шести сроков остаются в списке с возможностью выбора', async () => {
  open(); await choose();
  fireEvent.click(screen.getByRole('combobox', { name: 'Срок, мес.' }));
  fireEvent.click(await screen.findByRole('option', { name: '12' }));
  expect(screen.getByRole<HTMLInputElement>('combobox', { name: 'Срок, мес.' }).value).toBe('12');
});

it('показывает профиль только для чтения и предварительный платёж', async () => {
  open(); await choose();
  expect(screen.getByText('770112345695')).toBeTruthy();
  expect(screen.getByText(/Данные из ЕГР(ЮЛ|ИП) на/)).toBeTruthy();
  expect(screen.getByText(/По оборотам в нашем банке — около/)).toBeTruthy();
  expect(await screen.findByText(/Платёж в месяц ≈/)).toBeTruthy();
  expect(screen.getByText('Предварительный расчёт. Точные условия — после проверки заявки')).toBeTruthy();
});

it('серия вводов вызывает один расчёт через 400 мс с последней суммой', async () => {
  const bodies: components['schemas']['CalculatorRequest'][] = [];
  server.use(http.post('*/api/v1/calculator', async ({ request }) => {
    bodies.push(await request.json() as components['schemas']['CalculatorRequest']);
    return HttpResponse.json({ rate_estimate: 24, monthly_payment: 53558 });
  }));
  open(); await choose();
  await screen.findByText(/Платёж в месяц ≈/);
  bodies.length = 0;
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  const input = screen.getByLabelText('Сумма, ₽');
  fireEvent.change(input, { target: { value: '400000' } });
  await act(() => vi.advanceTimersByTimeAsync(200));
  fireEvent.change(input, { target: { value: '500000' } });
  await act(() => vi.advanceTimersByTimeAsync(200));
  fireEvent.change(input, { target: { value: '600000' } });
  await act(() => vi.advanceTimersByTimeAsync(399));
  expect(bodies).toHaveLength(0);
  await act(() => vi.advanceTimersByTimeAsync(1));
  vi.useRealTimers();
  await waitFor(() => expect(bodies).toEqual([{ product_code: 'EXPRESS', amount: 600000, term_months: 6 }]));
});

it('сумма за границами не отправляет ни расчёт, ни заявку и показывает ошибку', async () => {
  let submissions = 0;
  let calculations = 0;
  server.events.on('request:start', ({ request }) => {
    if (request.url.endsWith('/applications') && request.method === 'POST') submissions++;
    if (request.url.endsWith('/calculator')) calculations++;
  });
  open(); await choose();
  await screen.findByText(/Платёж в месяц ≈/);
  const previous = calculations;
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1' } });
  revenue();
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  expect(await screen.findByText(/Укажите целую сумму от/)).toBeTruthy();
  await act(() => new Promise((resolve) => setTimeout(resolve, 450)));
  expect(calculations).toBe(previous);
  expect(submissions).toBe(0);
  server.events.removeAllListeners('request:start');
});

it('Другое требует описание и показывает счётчик', async () => {
  open(); await choose('Другое'); revenue();
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  expect(await screen.findByText('Опишите цель: от 10 до 500 символов.')).toBeTruthy();
  expect(screen.getByText('0 / 500')).toBeTruthy();
});

it('выручка ноль не позволяет создать заявку', async () => {
  open(); await choose();
  fireEvent.change(screen.getByLabelText('Выручка за год, ₽'), { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  expect(await screen.findByText('Укажите выручку больше нуля в целых рублях.')).toBeTruthy();
});

it('422 сервера привязывает ошибку к полю', async () => {
  server.use(http.post('*/api/v1/applications', () => HttpResponse.json({ error: { code: 'VALIDATION_ERROR', message: 'Проверьте поля.', details: { fields: { amount: 'Уточните сумму для этого продукта.' } } } }, { status: 422 })));
  open(); await choose(); revenue();
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  expect(await screen.findByText('Уточните сумму для этого продукта.')).toBeTruthy();
  expect(screen.getByLabelText('Сумма, ₽').getAttribute('aria-invalid')).toBe('true');
});

it('создаёт черновик с выбранной компанией и открывает его карточку', async () => {
  let createdId = '';
  let body: components['schemas']['ApplicationCreate'] | undefined;
  server.events.on('request:start', async ({ request }) => {
    if (request.url.endsWith('/applications') && request.method === 'POST') body = await request.clone().json();
  });
  server.events.on('response:mocked', async ({ request, response }) => {
    if (request.url.endsWith('/applications') && request.method === 'POST' && response.status === 201) {
      const result: components['schemas']['ApplicationClient'] = await response.clone().json();
      createdId = result.id;
    }
  });
  open(); await choose(); revenue();
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  expect(await screen.findByRole('heading', { name: 'Карточка заявки' })).toBeTruthy();
  await waitFor(() => expect(createdId).not.toBe(''));
  expect(screen.getByTestId('location').textContent).toBe(`/app/applications/${createdId}`);
  expect(body).toEqual({ company_id: '20000000-0000-4000-8000-000000000001', product_code: 'EXPRESS', amount: 300000, term_months: 6, purpose: 'CASH_GAP', declared_revenue_year: 12000000 });
  server.events.removeAllListeners('response:mocked');
});

it('503 профиля блокирует создание, повтор загружает профиль', async () => {
  server.use(http.get('*/api/v1/companies/:id/profile', () => HttpResponse.json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Реестр недоступен.', details: {} } }, { status: 503 })));
  open();
  fireEvent.click(await screen.findByRole('button', { name: 'Оборудование и развитие' }));
  fireEvent.click(within(await screen.findByRole('region', { name: 'Экспресс-кредит' })).getByRole('button', { name: 'Выбрать' }));
  expect(await screen.findByText('Реестр временно недоступен, попробуйте позже')).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Создать заявку' }).disabled).toBe(true);
  server.resetHandlers(...createHandlers());
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Создать заявку' }).disabled).toBe(false));
});

async function restoredForm() {
  await screen.findByRole('heading', { name: 'Заявка на финансирование' });
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Создать заявку' }).disabled).toBe(false));
}

it('восстанавливает сумму, срок, цель, пояснение и выручку после перезагрузки формы', async () => {
  open(); await choose('Другое');
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1500000' } });
  revenue();
  fireEvent.change(screen.getByLabelText('Опишите цель'), { target: { value: 'Расширение мастерской' } });
  fireEvent.click(screen.getByRole('combobox', { name: 'Срок, мес.' }));
  fireEvent.click(await screen.findByRole('option', { name: '12' }));
  cleanup();
  open(); await restoredForm();
  expect(screen.getByRole<HTMLInputElement>('textbox', { name: 'Сумма, ₽' }).value).toBe('1 500 000');
  expect(screen.getByLabelText<HTMLInputElement>('Выручка за год, ₽').value).toBe('12 000 000');
  expect(screen.getByRole<HTMLInputElement>('combobox', { name: 'Срок, мес.' }).value).toBe('12');
  expect(screen.getByRole<HTMLInputElement>('combobox', { name: 'Цель' }).value).toBe('Другое');
  expect(screen.getByLabelText<HTMLTextAreaElement>('Опишите цель').value).toBe('Расширение мастерской');
});

it('после создания заявки удаляет сохранённую форму и открывает новую с начальными значениями', async () => {
  open(); const initialKeys = Object.keys(sessionStorage); await choose(); revenue();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1500000' } });
  expect(sessionStorage.length).toBeGreaterThan(initialKeys.length);
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  await screen.findByRole('heading', { name: 'Карточка заявки' });
  expect(Object.keys(sessionStorage)).toEqual(initialKeys);
  cleanup(); open(); await choose();
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('300 000');
  expect(screen.getByLabelText<HTMLInputElement>('Выручка за год, ₽').value).toBe('');
});

it('назад к выбору продукта очищает сохранённую форму', async () => {
  open(); const initialKeys = Object.keys(sessionStorage); await choose(); revenue();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1500000' } });
  expect(sessionStorage.length).toBeGreaterThan(initialKeys.length);
  fireEvent.click(screen.getByRole('button', { name: 'Назад к выбору продукта' }));
  expect(Object.keys(sessionStorage)).toEqual(initialKeys);
  fireEvent.click(within(await screen.findByRole('region', { name: 'Экспресс-кредит' })).getByRole('button', { name: 'Выбрать' }));
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('300 000');
  expect(screen.getByLabelText<HTMLInputElement>('Выручка за год, ₽').value).toBe('');
});

it('ошибка создания сохраняет введённую форму после перезагрузки', async () => {
  server.use(http.post('*/api/v1/applications', () => HttpResponse.json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Попробуйте позже.', details: {} } }, { status: 503 })));
  open(); await choose(); revenue();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1500000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  await screen.findByRole('alert');
  cleanup(); open(); await restoredForm();
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('1 500 000');
  expect(screen.getByLabelText<HTMLInputElement>('Выручка за год, ₽').value).toBe('12 000 000');
});

it('черновики разных продуктов восстанавливаются независимо без указателя последнего выбора', async () => {
  open(); await choose(); revenue();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1500000' } });
  const lastKey = Object.keys(sessionStorage).find(key => key.startsWith('application-form:last:'));
  expect(lastKey).toBeDefined();
  cleanup(); sessionStorage.removeItem(lastKey!); open(); await choose('Кассовый разрыв', 'Овердрафт');
  expect(screen.getByLabelText<HTMLInputElement>('Выручка за год, ₽').value).toBe('');
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '500000' } });
  cleanup(); sessionStorage.removeItem(lastKey!); open(); await choose();
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('1 500 000');
  cleanup(); sessionStorage.removeItem(lastKey!); open(); await choose('Кассовый разрыв', 'Овердрафт');
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('500 000');
});

it.each(['getItem', 'setItem', 'removeItem'] as const)('ошибка sessionStorage.%s не мешает созданию заявки', async (method) => {
  const original = Storage.prototype[method];
  vi.spyOn(Storage.prototype, method).mockImplementation(function (this: Storage, key: string, value?: string) {
    if (key.startsWith('application-form:')) throw new Error('Хранилище недоступно');
    return Reflect.apply(original, this, value === undefined ? [key] : [key, value]);
  });
  open(); await choose(); revenue();
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  expect(await screen.findByRole('heading', { name: 'Карточка заявки' })).toBeTruthy();
});

it('сумма с пробелами 1 500 000 отправляется в API целым числом 1500000', async () => {
  let body: components['schemas']['ApplicationCreate'] | undefined;
  server.events.on('request:start', async ({ request }) => {
    if (request.url.endsWith('/applications') && request.method === 'POST') body = await request.clone().json();
  });
  open(); await choose(); revenue();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1 500 000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  await screen.findByRole('heading', { name: 'Карточка заявки' });
  expect(body?.amount).toBe(1500000);
});

it('черновик отделён от другого пользователя той же компании', async () => {
  let me: components['schemas']['MeResponse'] | undefined;
  server.events.on('response:mocked', async ({ request, response }) => {
    if (request.url.endsWith('/me')) me = await response.clone().json();
  });
  open(); await choose(); revenue();
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1500000' } });
  await waitFor(() => expect(me).toBeDefined());
  const originalMe = me!;
  cleanup();
  server.use(http.get('*/api/v1/me', () => HttpResponse.json({ ...originalMe, user: { ...originalMe.user, id: 'another-user' } })));
  open(); await choose();
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('300 000');
  expect(screen.getByLabelText<HTMLInputElement>('Выручка за год, ₽').value).toBe('');
  cleanup(); server.resetHandlers(...createHandlers()); open(); await restoredForm();
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('1 500 000');
});

it.each(['{invalid', '{"amount":null}'])('повреждённый черновик %s не мешает работе формы', async (stored) => {
  open(); await choose(); revenue();
  const key = Object.keys(sessionStorage).find(key => key.startsWith('application-form:') && !key.startsWith('application-form:last:'));
  expect(key).toBeDefined();
  cleanup(); sessionStorage.setItem(key!, stored); open(); await restoredForm();
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('300 000');
  revenue(); fireEvent.click(screen.getByRole('button', { name: 'Создать заявку' }));
  expect(await screen.findByRole('heading', { name: 'Карточка заявки' })).toBeTruthy();
});

it('после перезагрузки сразу открывает форму последнего продукта с введённой суммой', async () => {
  open(); await choose();
  fireEvent.click(screen.getByRole('combobox', { name: 'Цель' }));
  fireEvent.click(await screen.findByRole('option', { name: 'Другое' }));
  fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '1500000' } });
  fireEvent.change(screen.getByLabelText('Опишите цель'), { target: { value: 'Расширение мастерской' } });
  const lastKey = Object.keys(sessionStorage).find(key => key.startsWith('application-form:last:'));
  expect(lastKey).toBeDefined();
  expect(JSON.parse(sessionStorage.getItem(lastKey!)!)).toEqual({ product_code: 'EXPRESS', purpose: 'OTHER' });
  cleanup(); open();
  expect(await screen.findByRole('heading', { name: 'Заявка на финансирование' })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: 'Зачем нужны деньги?' })).toBeNull();
  expect(screen.getByLabelText<HTMLInputElement>('Сумма, ₽').value).toBe('1 500 000');
  expect(screen.getByRole<HTMLInputElement>('combobox', { name: 'Цель' }).value).toBe('Другое');
  expect(screen.getByLabelText<HTMLTextAreaElement>('Опишите цель').value).toBe('Расширение мастерской');
});

it.each([
  '{invalid',
  JSON.stringify({ product_code: 'MISSING', purpose: 'CASH_GAP' }),
  JSON.stringify({ product_code: 'OVERDRAFT', purpose: 'EQUIPMENT' }),
])('недоступный или повреждённый последний выбор %s возвращает к выбору продукта', async (stored) => {
  open(); await choose();
  const lastKey = Object.keys(sessionStorage).find(key => key.startsWith('application-form:last:'));
  expect(lastKey).toBeDefined();
  cleanup(); sessionStorage.setItem(lastKey!, stored); open();
  expect(await screen.findByRole('heading', { name: 'Зачем нужны деньги?' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Кассовый разрыв' }));
  expect(await screen.findByRole('region', { name: 'Экспресс-кредит' })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: 'Заявка на финансирование' })).toBeNull();
});
