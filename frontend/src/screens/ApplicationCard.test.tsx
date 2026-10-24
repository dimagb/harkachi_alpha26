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
import { applications, applicationScenarios } from '../mocks/fixtures';
import { createHandlers } from '../mocks/handlers';
import { theme } from '../theme';

type Application = components['schemas']['ApplicationClient'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => server.resetHandlers(...createHandlers()));
afterAll(() => server.close());
afterEach(() => { cleanup(); setToken(null); vi.useRealTimers(); server.events.removeAllListeners(); });
function Location() { return <output aria-label="Маршрут">{useLocation().pathname + useLocation().hash}</output>; }
function open(application: Application, login = 'ip_good') {
  setToken(`demo:${login}`);
  render(<MantineProvider theme={theme} env="test"><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[`/app/applications/${application.id}`]}><App /><Location /></MemoryRouter></QueryClientProvider></MantineProvider>);
}
function fixture(state: Application['state']) {
  return applicationScenarios.find((item) => item.state === state)!;
}
function serve(application: Application) { server.use(http.get('*/api/v1/applications/:id', () => HttpResponse.json<Application>(application))); }

it.each([[22, '22\u00a0%'], [21.5, '21,5\u00a0%']])('ставка %s без лишних нулей', async (rate, expected) => {
  const application = { ...applications[0]!, offer: { ...applications[0]!.offer!, rate: Number(rate) } };
  serve(application); open(application);
  const figures = await screen.findByRole('region', { name: 'Ключевые цифры' });
  expect(within(figures).getByText(String(expected).replace(/\s/g, ' '))).toBeTruthy();
});

it('светлый бейдж действия и источник сведений о компании', async () => {
  const application = fixture('INFO_REQUESTED'); serve(application); open(application);
  const labels = await screen.findAllByText('Нужно ваше действие');
  const badge = labels.map((label) => label.closest<HTMLElement>('[data-variant]')).find(Boolean);
  expect(badge?.dataset.variant).toBe('light');
  expect(badge?.style.background).toBe('var(--mantine-color-wait-0)');
  expect(badge?.style.borderColor).toBe('var(--mantine-color-wait-2)');
  expect(await screen.findByText('Данные из ЕГРИП на 23.10.2026')).toBeTruthy();
});

it.each([
  ['VALIDATION', 'Идёт сейчас: Проверка данных'],
  ['INFO_REQUESTED', 'Банк попросил уточнить данные'],
  ['OFFER_ISSUED', 'Предложение готово'],
  ['DECLINED', 'Банк отказал'],
  ['DISBURSED', 'Деньги зачислены'],
] as const)('история %s: фраза, дата заголовка, время строки', async (state, phrase) => {
  const application = fixture(state); serve(application); open(application);
  const history = await screen.findByRole('region', { name: 'История заявки' });
  expect(within(history).getByText(phrase)).toBeTruthy();
  expect(within(history).getByText('23.10.2026')).toBeTruthy();
  const rows = within(history).getAllByRole('listitem');
  for (const row of rows) expect(row.querySelector('time')?.textContent).toMatch(/^\d{2}:\d{2}$/);
  expect(within(history).getByText('Заявка отправлена')).toBeTruthy();
});

it('VALIDATION: шесть серверных этапов, текущая проверка и панель без кнопки', async () => {
  const application = fixture('VALIDATION'); serve(application); open(application);
  const timeline = await screen.findByRole('list', { name: 'Этапы заявки' });
  const stages = within(timeline).getAllByRole('listitem');
  expect(stages).toHaveLength(6);
  expect(stages[0]!.getAttribute('data-status')).toBe('done');
  expect(stages[1]!.textContent).toContain('Идёт сейчас');
  for (const stage of stages.slice(2)) expect(stage.textContent).toContain('Ожидает');
  const panel = screen.getByRole('region', { name: 'Что происходит с заявкой' });
  expect(within(panel).getByText('Проверяем данные заявки')).toBeTruthy();
  expect(within(panel).getByText('Ничего, мы сообщим, когда понадобится ваше участие')).toBeTruthy();
  expect(within(panel).queryByRole('link')).toBeNull();
  const badge = screen.getByText('Проверяем заявку').closest<HTMLElement>('[data-variant]');
  expect(badge?.style.background).toBe('var(--mantine-color-gray-0)');
  expect(badge?.style.color).toBe('var(--mantine-color-gray-7)');
});

it('опрос каждые 2 с сам показывает предложение и прекращается в OFFER_ISSUED', async () => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
  const validation = fixture('VALIDATION');
  let requests = 0;
  server.use(http.get('*/api/v1/applications/:id', () => HttpResponse.json(++requests === 1 ? validation : { ...applications[0]!, id: validation.id })));
  open(validation);
  await screen.findByText('Проверяем данные заявки');
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(await screen.findByRole('link', { name: 'Посмотреть предложение' })).toBeTruthy();
  const afterOffer = requests;
  await act(() => vi.advanceTimersByTimeAsync(5000));
  expect(requests).toBe(afterOffer);
});

it.each([['APPROVED', 'ok'], ['COUNTER', 'wait']] as const)('панель предложения %s имеет тон %s', async (kind, tone) => {
  const application = { ...applications[0]!, offer: { ...applications[0]!.offer!, kind } };
  serve(application); open(application);
  expect((await screen.findByRole('region', { name: 'Что происходит с заявкой' })).getAttribute('data-tone')).toBe(tone);
});

it('INFO_REQUESTED: второму этапу нужно действие, ссылка ведёт к вопросам банка', async () => {
  const application = fixture('INFO_REQUESTED'); serve(application); open(application);
  const link = await screen.findByRole('link', { name: 'Ответить на вопросы банка' });
  const stages = within(screen.getByRole('list', { name: 'Этапы заявки' })).getAllByRole('listitem');
  expect(stages[1]!.textContent).toContain('Нужно ваше действие');
  fireEvent.click(link);
  expect(screen.getByLabelText('Маршрут').textContent).toBe(`/app/applications/${application.id}#info-request`);
  expect(within(screen.getByRole('region', { name: 'Вопросы банка' })).getByRole('button', { name: 'Отправить ответ' })).toBeTruthy();
});

it('COUNTER: сумма и срок в шапке и цифрах из offer, точные ставка и платёж', async () => {
  const application = applications[1]!; serve(application); open(application, 'ooo_load');
  const headline = await screen.findByRole('heading', { name: /Банк готов выдать/ });
  expect(headline.textContent?.replace(/\s/g, ' ')).toContain('2 850 000 ₽');
  expect(headline.textContent).toContain('24 мес.');
  const figures = screen.getByRole('region', { name: 'Ключевые цифры' });
  expect(figures.textContent?.replace(/\s/g, ' ')).toContain('149 264 ₽');
  expect(figures.textContent).toContain('23\u00a0%');
  expect(figures.textContent).not.toContain('около');
});

it('DECLINED: отказ на четвёртом этапе и только публичная причина', async () => {
  const application = fixture('DECLINED'); serve(application); open(application);
  const decision = await screen.findByRole('region', { name: 'Что происходит с заявкой' });
  expect(within(decision).getByRole('link', { name: 'Подать новую заявку' })).toBeTruthy();
  const stages = within(screen.getByRole('list', { name: 'Этапы заявки' })).getAllByRole('listitem');
  expect(stages[3]!.textContent).toContain('Отказ');
  expect(screen.getByText(application.client_reason!.text)).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/SF_ADDITIONAL|risk_flag|internal_reasons|rules_fired|inputs_snapshot|route_reason/);
});

it('WITHDRAWN: отменённый этап, отзыва нет', async () => {
  const application = fixture('WITHDRAWN'); serve(application); open(application);
  await screen.findByText('Заявка отозвана');
  expect(within(screen.getByRole('list', { name: 'Этапы заявки' })).getAllByRole('listitem').some((item) => item.textContent?.includes('Отменено'))).toBe(true);
  expect(screen.queryByRole('button', { name: 'Отозвать заявку' })).toBeNull();
});

it('отзыв подтверждается в модальном окне и обновляет карточку из ответа', async () => {
  const application = applications[0]!; open(application);
  fireEvent.click(await screen.findByRole('button', { name: 'Отозвать заявку' }));
  const dialog = await screen.findByRole('dialog');
  expect(dialog.textContent).toContain(`Отозвать заявку № ${application.number}? Это действие нельзя отменить.`);
  fireEvent.click(within(dialog).getByRole('button', { name: 'Отозвать' }));
  expect(await screen.findByText('Отозвана')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Отозвать заявку' })).toBeNull();
});

it('Не отзывать не отправляет запрос', async () => {
  let withdrawals = 0;
  server.events.on('request:start', ({ request }) => { if (request.url.endsWith('/withdraw')) withdrawals++; });
  open(applications[0]!);
  fireEvent.click(await screen.findByRole('button', { name: 'Отозвать заявку' }));
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Не отзывать' }));
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(withdrawals).toBe(0);
});

it('409 при отзыве сообщает об изменении и перезагружает карточку', async () => {
  let reads = 0;
  const application = applications[0]!;
  server.use(http.get('*/api/v1/applications/:id', () => { reads++; return HttpResponse.json(application); }), http.post('*/api/v1/applications/:id/withdraw', () => HttpResponse.json({ error: { code: 'INVALID_TRANSITION', message: 'Переход недоступен.', details: {} } }, { status: 409 })));
  open(application);
  fireEvent.click(await screen.findByRole('button', { name: 'Отозвать заявку' }));
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Отозвать' }));
  expect(await screen.findByText('Заявка уже изменилась')).toBeTruthy();
  await waitFor(() => expect(reads).toBe(2));
});

it('бухгалтеру без can_sign не показывает кнопку предложения', async () => {
  const application = applicationScenarios.find((item) => item.stage.what_to_do === 'Ждём решения подписанта компании')!;
  open(application, 'ooo_load_accountant');
  expect(await screen.findByText('Ждём решения подписанта компании')).toBeTruthy();
  expect(within(screen.getByRole('region', { name: 'Что происходит с заявкой' })).queryByRole('link')).toBeNull();
});

it('404: заявка не найдена и ссылка к списку', async () => {
  open({ ...applications[0]!, id: 'missing' });
  expect(await screen.findByRole('heading', { name: 'Заявка не найдена' })).toBeTruthy();
  expect(screen.getByRole('link', { name: 'К моим заявкам' }).getAttribute('href')).toBe('/app');
});

it('без оферты делает один расчёт, показывает около, историю по убыванию времени', async () => {
  const application = fixture('MANUAL_REVIEW'); serve(application);
  let calculations = 0;
  server.events.on('request:start', ({ request }) => { if (request.url.endsWith('/calculator')) calculations++; });
  open(application);
  const figures = await screen.findByRole('region', { name: 'Ключевые цифры' });
  await waitFor(() => expect(figures.textContent).toContain('около 24\u00a0%'));
  expect(calculations).toBe(1);
  const history = screen.getByRole('list', { name: 'История этапов' });
  expect(within(history).getAllByRole('listitem')[0]!.textContent).toContain('Идёт сейчас: Оценка');
  expect(within(history).getAllByRole('listitem')).toHaveLength(3);
});

it('овердрафт показывает проценты за использованные дни вместо платежа', async () => {
  const base = applications[0]!;
  const application: Application = { ...base, product_code: 'OVERDRAFT', term_months: 12, offer: { ...base.offer!, product_code: 'OVERDRAFT', term_months: 12, monthly_payment: null } };
  serve(application); open(application);
  const figures = await screen.findByRole('region', { name: 'Ключевые цифры' });
  expect(within(figures).getByText('Проценты — только за использованные дни')).toBeTruthy();
});

it('ошибка загрузки позволяет повторить запрос', async () => {
  const application = applications[0]!;
  server.use(http.get('*/api/v1/applications/:id', () => HttpResponse.json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Попробуйте позже', details: {} } }, { status: 503 })));
  open(application);
  expect(await screen.findByText('Не удалось загрузить заявку. Попробуйте ещё раз.')).toBeTruthy();
  server.resetHandlers(...createHandlers());
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
  expect(await screen.findByRole('link', { name: 'Посмотреть предложение' })).toBeTruthy();
});

it('при смене пользователя не показывает кэш чужой заявки до ответа сервера', async () => {
  let finish = () => {};
  const pending = new Promise<void>((resolve) => { finish = resolve; });
  server.use(http.get('*/api/v1/applications/:id', async ({ request }) => {
    if (request.headers.get('Authorization') === 'Bearer demo:ooo_load') {
      await pending;
      return HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Заявка не найдена.', details: {} } }, { status: 404 });
    }
    return HttpResponse.json(applications[0]!);
  }));
  open(applications[0]!);
  await screen.findByRole('link', { name: 'Посмотреть предложение' });
  act(() => setToken('demo:ooo_load'));
  try {
    await screen.findByText('Петров Илья Игоревич');
    expect(await screen.findByText('Загружаем заявку…')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Посмотреть предложение' })).toBeNull();
  } finally { finish(); }
  expect(await screen.findByRole('heading', { name: 'Заявка не найдена' })).toBeTruthy();
});
