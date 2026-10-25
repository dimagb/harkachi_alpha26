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
import { accounts, applications, applicationScenarios, companyProfiles } from '../../../mocks/fixtures';
import { createHandlers } from '../../../mocks/handlers';
import { createDecisionHandlers } from '../../../mocks/client/decision';
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
it('ip_bad: название, ИНН и ОГРН компании совпадают с personas.json', () => {
  const personas = JSON.parse(readFileSync('../contracts/personas.json', 'utf8')) as { personas: { code: string; name: string; inn: string; ogrn: string }[] };
  const persona = personas.personas.find((p) => p.code === 'ip_bad')!;
  const company = accounts.ip_bad!.companies[0]!.company;
  expect(company).toMatchObject({ name: persona.name, inn: persona.inn });
  expect(companyProfiles[company.id]).toMatchObject({ name: persona.name, inn: persona.inn, ogrn: persona.ogrn });
});
it.each(['OFFER_ISSUED', 'SIGNING', 'DISBURSED'] as const)('%s с офертой: параметры содержат пять строк исходной заявки без плиток', async (state) => {
  const application = { ...applications[1]!, state };
  serve(application); open(application, 'ooo_load');
  const params = await screen.findByRole('region', { name: 'Параметры заявки' });
  expect([...params.querySelectorAll('dt')].map((element) => element.textContent)).toEqual(['Сумма заявки', 'Срок', 'Цель', 'Выручка за год', 'Компания']);
  const values = [...params.querySelectorAll('dd')];
  expect(values[0]!.textContent?.replace(/\s/g, ' ')).toBe('4 000 000 ₽');
  expect(values[1]!.textContent).toBe('12 мес.');
  expect(values[2]!.textContent).toBe('Оборотные средства');
  expect(values[3]!.textContent?.replace(/\s/g, ' ')).toBe('24 000 000 ₽');
  expect(values[4]!.textContent).toContain('ООО «Северный склад»');
  expect(within(params).queryByRole('region', { name: 'Ключевые цифры' })).toBeNull();
  expect(params.textContent).not.toContain('Ставка');
  expect(params.textContent).not.toContain('Платёж');
});
it('COUNTER: единственная карточка сравнения содержит срок действия и действия, объяснение остаётся рядом', async () => {
  open(applications[1]!, 'ooo_load');
  const comparison = await screen.findByRole('region', { name: 'Сравнение условий' });
  expect(screen.queryByRole('region', { name: 'Условия' })).toBeNull();
  expect(within(comparison).getByText('Предложение действует до 30.10.2026')).toBeTruthy();
  expect(within(comparison).getByRole('button', { name: 'Принять предложение' })).toBeTruthy();
  expect(within(comparison).getByRole('button', { name: 'Отказаться' })).toBeTruthy();
  expect(screen.getByRole('region', { name: 'Почему одобрили' })).toBeTruthy();
});
it.each([
  { state: 'DECLINED', withOffer: false }, { state: 'DECLINED', withOffer: true },
  { state: 'WITHDRAWN', withOffer: false }, { state: 'WITHDRAWN', withOffer: true },
  { state: 'EXPIRED', withOffer: false }, { state: 'EXPIRED', withOffer: true },
] as const)('$state, offer=$withOffer: нет оценочных плиток и запросов /calculator', async ({ state, withOffer }) => {
  let calculations = 0;
  server.events.on('request:start', ({ request }) => { if (request.url.endsWith('/calculator')) calculations++; });
  const application: Application = { ...applications[1]!, state, offer: withOffer ? applications[1]!.offer : null, allowed_actions: ['NEW_APPLICATION'] };
  serve(application); open(application, 'ooo_load');
  await screen.findByText('Данные из ЕГРЮЛ на 23.10.2026');
  const params = screen.getByRole('region', { name: 'Параметры заявки' });
  expect(within(params).queryByRole('region', { name: 'Ключевые цифры' })).toBeNull();
  expect(params.textContent).not.toContain('около');
  expect(calculations).toBe(0);
});
it('DECLINED: новая заявка предлагается один раз в панели, снизу только возврат к списку', async () => {
  open({ ...applications[0]!, id: badId }, 'ip_bad');
  await screen.findByRole('heading', { name: 'Банк не может выдать кредит сейчас' });
  expect(screen.getAllByRole('link', { name: 'Подать новую заявку' })).toHaveLength(1);
  expect(within(screen.getByRole('region', { name: 'Что происходит с заявкой' })).getByRole('link', { name: 'Подать новую заявку' })).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Вернуться к заявкам' }).getAttribute('href')).toBe('/app');
  expect(within(screen.getByRole('region', { name: 'Параметры заявки' })).getByRole('link', { name: 'Вернуться к заявкам' })).toBeTruthy();
});
it('DECLINED: пересмотр — последняя строка внутри карточки причины', async () => {
  open({ ...applications[0]!, id: badId }, 'ip_bad');
  const reason = await screen.findByRole('region', { name: 'Причина отказа' });
  const objection = within(reason).getByRole('region', { name: 'Пересмотр решения' });
  expect(within(objection).getByText('Не согласны с решением?')).toBeTruthy();
  expect(within(objection).getByText('Его пересмотрит специалист банка')).toBeTruthy();
  expect(within(objection).getByRole('button', { name: 'Попросить пересмотр' }).getAttribute('data-variant')).toBe('default');
  const advice = within(reason).getByRole('heading', { name: 'Что можно сделать' });
  expect(advice.compareDocumentPosition(objection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getAllByRole('button', { name: 'Попросить пересмотр' })).toHaveLength(1);
});
it.each([
  ['не ИП', 'ooo_load'], ['срок пересмотра вышел', 'ip_good'],
] as const)('DECLINED, %s: нет строки приглашения без доступного пересмотра', async (_case, login) => {
  const declined = await (await fetch(`http://localhost/api/v1/applications/${badId}`, { headers: { Authorization: 'Bearer demo:ip_bad' } })).json() as Application;
  const application: Application = { ...applications[0]!, state: 'DECLINED', offer: null, allowed_actions: ['NEW_APPLICATION'], client_reason: declined.client_reason };
  serve(application); open(application, login);
  await screen.findByRole('region', { name: 'Причина отказа' });
  expect(screen.queryByText('Не согласны с решением?')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Попросить пересмотр' })).toBeNull();
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
it('два вопроса специалиста с одинаковым кодом получают отдельные ответы без value и закрывают запрос', async () => {
  let body: unknown;
  const base = applicationScenarios.find((a) => a.state === 'INFO_REQUESTED')!;
  const application: Application = { ...base, info_request: { ...base.info_request!, items: [
    { item_code: 'UNDERWRITER_QUESTION', question: 'Первый вопрос специалиста', requires_value: false },
    { item_code: 'UNDERWRITER_QUESTION', question: 'Второй вопрос специалиста', requires_value: false },
  ] } };
  server.use(...createDecisionHandlers(new Map([[application.id, application]])));
  server.events.on('request:start', async ({ request }) => { if (request.url.endsWith('/info-response')) body = await request.clone().json(); });
  open(application);
  const section = await screen.findByRole('region', { name: 'Вопросы банка' });
  fireEvent.change(within(within(section).getByRole('group', { name: 'Первый вопрос специалиста' })).getByLabelText('Ответ'), { target: { value: 'Первый ответ' } });
  fireEvent.change(within(within(section).getByRole('group', { name: 'Второй вопрос специалиста' })).getByLabelText('Ответ'), { target: { value: 'Второй ответ' } });
  fireEvent.click(within(section).getByRole('button', { name: 'Отправить ответ' }));
  await screen.findByText('Проверяем данные заявки');
  expect(screen.queryByRole('region', { name: 'Вопросы банка' })).toBeNull();
  expect(body).toEqual({ answers: [
    { item_code: 'UNDERWRITER_QUESTION', comment: 'Первый ответ' },
    { item_code: 'UNDERWRITER_QUESTION', comment: 'Второй ответ' },
  ] });
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
  expect(screen.queryByText('Не согласны с решением?')).toBeNull();
});
