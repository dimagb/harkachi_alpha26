import { readFileSync } from 'node:fs';
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router';
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import App from '../../../App';
import type { components } from '../../../api/schema';
import { setToken } from '../../../auth/session';
import { applications, applicationScenarios } from '../../../mocks/fixtures';
import { createHandlers } from '../../../mocks/handlers';
import { theme } from '../../../theme';

type Application = components['schemas']['ApplicationClient'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => server.resetHandlers(...createHandlers()));
afterAll(() => server.close());
afterEach(() => { cleanup(); setToken(null); server.events.removeAllListeners(); vi.restoreAllMocks(); });
function open(application = applications[0]!, login = 'ip_good') {
  setToken(`demo:${login}`);
  render(<MantineProvider theme={theme} env="test"><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[`/app/applications/${application.id}`]}><App /></MemoryRouter></QueryClientProvider></MantineProvider>);
}
function serve(application: Application) { server.use(http.get('*/api/v1/applications/:id', () => HttpResponse.json(application))); }
const badId = '30000000-0000-4000-8000-000000000201';
const amlId = '30000000-0000-4000-8000-000000000202';
function error(status: number, code: string, details = {}) { return HttpResponse.json({ error: { code, message: 'Проверьте данные.', details } }, { status }); }

it.each([['ip_good', 0], ['ooo_load', 1]] as const)('%s: оферта сверяется с golden personas.json', (code, index) => {
  const personas = JSON.parse(readFileSync('../contracts/personas.json', 'utf8')) as { personas: { code: string; demo: { expected: { offer?: Record<string, number> } } }[] };
  expect(applications[index]!.offer).toMatchObject(personas.personas.find((p) => p.code === code)!.demo.expected.offer!);
});
it('одобрение показывает условия, срок действия и три объяснения', async () => {
  open();
  expect(await screen.findByRole('heading', { name: /Банк одобрил 1\s500\s000\s₽/ })).toBeTruthy();
  const decision = screen.getByRole('region', { name: 'Решение банка' });
  for (const text of ['22 %', '24 мес.', '77 817 ₽', 'Предложение действует до 30.10.2026']) expect(within(decision).getByText(text)).toBeTruthy();
  expect(within(screen.getByRole('region', { name: 'Почему одобрили' })).getAllByRole('listitem')).toHaveLength(3);
});
it('принятие отправляет только версию оферты, показывает SIGNING и сохраняется после чтения', async () => {
  let body: unknown;
  server.events.on('request:start', async ({ request }) => { if (request.url.endsWith('/offer/accept')) body = await request.clone().json(); });
  open();
  fireEvent.click(await screen.findByRole('button', { name: 'Принять предложение' }));
  expect(await screen.findByText('Готовим договор к подписанию')).toBeTruthy();
  expect(body).toEqual({ offer_version: 1 });
  expect(screen.queryByRole('button', { name: 'Принять предложение' })).toBeNull();
});
it.each([[409, 'CONFLICT_VERSION', 'Условия изменились — проверьте их ещё раз'], [409, 'OFFER_EXPIRED', 'Срок предложения истёк'], [501, 'NOT_IMPLEMENTED', 'Действие пока недоступно, попробуйте позже']] as const)('%s %s: понятная ошибка и повторное чтение при конфликте', async (status, code, text) => {
  let reads = 0;
  server.use(http.get('*/api/v1/applications/:id', () => { reads++; return HttpResponse.json(applications[0]!); }), http.post('*/api/v1/applications/:id/offer/accept', () => error(status, code)));
  open(); fireEvent.click(await screen.findByRole('button', { name: 'Принять предложение' }));
  expect(await screen.findByText(text)).toBeTruthy();
  await waitFor(() => expect(reads).toBe(status === 409 ? 2 : 1));
});
it('отказ требует подтверждения; возврат не отправляет запрос, подтверждение закрывает заявку', async () => {
  let requests = 0;
  server.events.on('request:start', ({ request }) => { if (request.url.endsWith('/offer/reject')) requests++; });
  open(); fireEvent.click(await screen.findByRole('button', { name: 'Отказаться' }));
  let dialog = await screen.findByRole('dialog');
  expect(dialog.textContent).toContain('Заявка будет закрыта, это действие нельзя отменить');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Вернуться' }));
  expect(requests).toBe(0);
  fireEvent.click(screen.getByRole('button', { name: 'Отказаться' }));
  dialog = await screen.findByRole('dialog');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Отказаться' }));
  expect(await screen.findByText('Вы отказались от предложения')).toBeTruthy();
  expect(requests).toBe(1);
  expect(screen.getByText('Отозвана')).toBeTruthy();
});
it('встречное сравнивает запрошенные и предложенные условия, запрашивает расчёт и поясняет поручительство', async () => {
  let calculation: unknown;
  server.events.on('request:start', async ({ request }) => { if (request.url.endsWith('/calculator')) calculation = await request.clone().json(); });
  open(applications[1]!, 'ooo_load');
  await screen.findByRole('heading', { name: /Банк готов выдать 2\s850\s000\s₽ на 24 мес\./ });
  const requested = screen.getByRole('region', { name: 'Вы просили' });
  expect(within(requested).getByText('4 000 000 ₽')).toBeTruthy();
  expect(await within(requested).findByText(/^около .* ₽$/)).toBeTruthy();
  expect(within(requested).queryByText('Ставка')).toBeNull();
  expect(calculation).toEqual({ product_code: 'WORKING_CAPITAL', amount: 4000000, term_months: 12 });
  expect(screen.getByText('Для ООО нужен поручитель — учредитель с долей больше 50%. Поручительство подписывается на следующем шаге')).toBeTruthy();
  expect(screen.getByText(applications[1]!.offer!.counter_reason!)).toBeTruthy();
});
it('бухгалтер видит условия и пояснение права подписи без кнопок оферты', async () => {
  open(applications[1]!, 'ooo_load_accountant');
  expect(await screen.findByText('Принять предложение может руководитель или сотрудник с правом подписи')).toBeTruthy();
  expect(screen.getByRole('region', { name: 'Мы предлагаем' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Принять предложение' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Отказаться' })).toBeNull();
});
it('просрочка: причина, действие, дата; пересмотр требует 10 символов и показывает ожидание', async () => {
  let body: unknown;
  server.events.on('request:start', async ({ request }) => { if (request.url.endsWith('/objection')) body = await request.clone().json(); });
  open({ ...applications[0]!, id: badId }, 'ip_bad');
  await screen.findByRole('heading', { name: 'Банк не может выдать кредит сейчас' });
  expect(screen.getByText('Кредитная история')).toBeTruthy();
  expect(screen.getByText('Есть просроченная задолженность по кредитам')).toBeTruthy();
  expect(screen.getByText('Погасите просрочку и подайте заявку повторно через 30 дней')).toBeTruthy();
  expect(screen.getByText('Подать новую заявку можно с 23.11.2026')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Попросить пересмотр' }));
  const dialog = await screen.findByRole('dialog');
  const input = within(dialog).getByLabelText('Почему вы не согласны');
  fireEvent.change(input, { target: { value: '123456789' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Отправить обращение' }));
  expect(within(dialog).getByText('Введите от 10 до 2000 символов')).toBeTruthy();
  expect(body).toBeUndefined();
  fireEvent.change(input, { target: { value: 'Просрочка уже погашена' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Отправить обращение' }));
  expect(await screen.findByText('Ваше обращение рассматривает специалист банка')).toBeTruthy();
  expect(body).toEqual({ text: 'Просрочка уже погашена' });
});
it('дополнительные проверки: только публичная причина без пересмотра', async () => {
  open({ ...applications[1]!, id: amlId }, 'ooo_aml');
  expect(await screen.findByText('Заявка не прошла дополнительные проверки банка')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Попросить пересмотр' })).toBeNull();
  expect(document.body.textContent).not.toMatch(/SF_ADDITIONAL|risk_flag|internal_reasons/);
});
it.each([501, 'network'] as const)('ошибка пересмотра %s видна внутри диалога и сохраняет текст обращения', async (status) => {
  server.use(http.post('*/api/v1/applications/:id/objection', () => status === 501 ? error(501, 'NOT_IMPLEMENTED') : HttpResponse.error()));
  open({ ...applications[0]!, id: badId }, 'ip_bad');
  fireEvent.click(await screen.findByRole('button', { name: 'Попросить пересмотр' }));
  const dialog = await screen.findByRole('dialog');
  const input = within(dialog).getByLabelText<HTMLTextAreaElement>('Почему вы не согласны');
  fireEvent.change(input, { target: { value: 'Просрочка уже погашена' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Отправить обращение' }));
  expect(await within(dialog).findByText(status === 501 ? 'Действие пока недоступно, попробуйте позже' : 'Не удалось отправить обращение. Проверьте соединение и попробуйте ещё раз.')).toBeTruthy();
  expect(input.value).toBe('Просрочка уже погашена');
});
it('фикстура отказа загружает сведения о своей компании без уведомления об ошибке', async () => {
  open({ ...applications[0]!, id: badId }, 'ip_bad');
  expect(await screen.findByText('Данные из ЕГРИП на 23.10.2026')).toBeTruthy();
  expect(screen.queryByText('Компания не найдена.')).toBeNull();
});
it('дозапрос проверяет выручку и комментарий, отправляет точное тело и возвращает проверку', async () => {
  let body: unknown;
  server.events.on('request:start', async ({ request }) => { if (request.url.endsWith('/info-response')) body = await request.clone().json(); });
  open(applicationScenarios.find((a) => a.state === 'INFO_REQUESTED')!);
  const section = await screen.findByRole('region', { name: 'Вопросы банка' });
  const submit = within(section).getByRole('button', { name: 'Отправить ответ' });
  fireEvent.click(submit);
  expect(within(section).getByText('Укажите целую выручку больше нуля')).toBeTruthy();
  fireEvent.change(within(section).getByLabelText('Выручка за год, ₽'), { target: { value: '14000000' } });
  fireEvent.change(within(section).getByLabelText('Пояснение'), { target: { value: 'Да' } });
  fireEvent.click(submit);
  expect(within(section).getByText('Введите от 3 до 1000 символов')).toBeTruthy();
  expect(body).toBeUndefined();
  fireEvent.change(within(section).getByLabelText('Пояснение'), { target: { value: 'Часть выручки в другом банке' } });
  fireEvent.click(submit);
  await screen.findByText('Проверяем данные заявки');
  expect(body).toEqual({ answers: [{ item_code: 'REVENUE_CONFIRM', value: 14000000, comment: 'Часть выручки в другом банке' }] });
  expect(screen.queryByRole('region', { name: 'Вопросы банка' })).toBeNull();
  expect(within(screen.getByRole('list', { name: 'Этапы заявки' })).getByText('Идёт сейчас')).toBeTruthy();
});
it.each([409, 422])('дозапрос %s: закрытие перезагружает данные, валидация показывает ошибку поля', async (status) => {
  const application = applicationScenarios.find((a) => a.state === 'INFO_REQUESTED')!;
  let reads = 0;
  server.use(http.get('*/api/v1/applications/:id', () => { reads++; return HttpResponse.json(application); }), http.post('*/api/v1/applications/:id/info-response', () => error(status, status === 409 ? 'INVALID_TRANSITION' : 'VALIDATION_ERROR', { fields: { 'answers.0.comment': 'Уточните пояснение' } })));
  open(application);
  const section = await screen.findByRole('region', { name: 'Вопросы банка' });
  fireEvent.change(within(section).getByLabelText('Выручка за год, ₽'), { target: { value: '14000000' } });
  fireEvent.change(within(section).getByLabelText('Пояснение'), { target: { value: 'Часть выручки в другом банке' } });
  fireEvent.click(within(section).getByRole('button', { name: 'Отправить ответ' }));
  expect(await screen.findByText(status === 409 ? 'Запрос уже закрыт' : 'Уточните пояснение')).toBeTruthy();
  await waitFor(() => expect(reads).toBe(status === 409 ? 2 : 1));
});
it('кнопка панели плавно прокручивает к предложению', async () => {
  const scroll = vi.fn();
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scroll });
  open(); fireEvent.click(await screen.findByRole('link', { name: 'Посмотреть предложение' }));
  expect(scroll).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
});
it('завершённое обращение показывает outcome_text и не предлагает повторный пересмотр', async () => {
  const application = { ...applications[0]!, state: 'DECLINED' as const, offer: null, objection: { status: 'RESOLVED' as const, created_at: '2026-10-24T09:00:00Z', outcome_text: 'Решение проверено специалистом' }, allowed_actions: ['NEW_APPLICATION' as const] };
  serve(application); open(application);
  expect(await screen.findByText('Решение проверено специалистом')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Попросить пересмотр' })).toBeNull();
});
