import { MantineProvider } from '@mantine/core';
import { cleanup, fireEvent, render, screen, waitFor, within, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { useState } from 'react';
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { components } from '../../../api/schema';
import { setToken } from '../../../auth/session';
import { accounts, applications, draftApplication } from '../../../mocks/fixtures';
import SubmitSection from './SubmitSection';

type Application = components['schemas']['ApplicationClient'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
afterEach(() => { cleanup(); setToken(null); server.resetHandlers(); vi.useRealTimers(); });
function open(login = 'ip_good', awaiting = false) {
  const base = applications[login === 'ip_good' ? 0 : 1]!;
  const application = { ...draftApplication(base, base.id, base.number), awaiting_signature: awaiting, allowed_actions: login === 'ooo_load_accountant' ? awaiting ? [] : ['REQUEST_SIGNATURE'] : ['SUBMIT'] } as Application;
  setToken(`demo:${login}`);
  function Host() {
    const [data, setData] = useState(application);
    return <SubmitSection application={data} companyKind={accounts[login]!.companies[0]!.company.kind} onUpdate={setData} onReload={async () => {}} onMessage={() => {}} />;
  }
  render(<MantineProvider env="test"><Host /></MantineProvider>);
  return application;
}
function otp(expires = Date.now() + 300000) { server.use(http.post('*/api/v1/applications/:id/otp', () => HttpResponse.json({ otp_id: 'otp-1', demo_code: '123456', expires_at: new Date(expires).toISOString() }))); }
async function consentAndCode() {
  fireEvent.click(screen.getByRole('checkbox', { name: 'Согласен: обработка персональных данных' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Согласен: запрос кредитной истории' }));
  fireEvent.click(screen.getByRole('button', { name: 'Подписать и отправить' }));
  fireEvent.click(screen.getByRole('button', { name: 'Получить код' }));
  await screen.findByLabelText('Код из SMS');
}
it.each(['ip_good', 'ooo_load'])('%s: обязательные согласия, отдельные документы и точное тело подачи', async (login) => {
  otp(); const application = open(login);
  const region = screen.getByRole('region', { name: 'Согласия и отправка' });
  expect(within(region).getAllByRole('checkbox')).toHaveLength(login === 'ip_good' ? 3 : 2);
  expect((screen.getByRole('button', { name: 'Подписать и отправить' }) as HTMLButtonElement).disabled).toBe(true);
  let submitted: unknown;
  server.use(http.post('*/api/v1/applications/:id/submit', async ({ request }) => {
    submitted = await request.json(); return HttpResponse.json({ ...application, state: 'SUBMITTED' });
  }));
  await consentAndCode();
  expect(screen.getByText('Демо-режим: код 123456')).toBeTruthy();
  expect(document.activeElement).toBe(screen.getByLabelText('Код из SMS'));
  fireEvent.change(screen.getByLabelText('Код из SMS'), { target: { value: '1a2345678' } });
  expect((screen.getByLabelText('Код из SMS') as HTMLInputElement).value).toBe('123456');
  fireEvent.click(screen.getByRole('button', { name: 'Подставить' }));
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить и отправить' }));
  await waitFor(() => expect(submitted).toEqual({ otp_id: 'otp-1', code: '123456', consents: { pdn: true, bki: true, auto_decision: false } }));
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Согласия и отправка' })).toBeNull());
});
it('ИП может отдельно согласиться на автоматическое решение', async () => {
  otp(); open(); let submitted: unknown;
  server.use(http.post('*/api/v1/applications/:id/submit', async ({ request }) => { submitted = await request.json(); return HttpResponse.json({ ...applications[0]!, state: 'SUBMITTED' }); }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Согласен: автоматическое решение' }));
  await consentAndCode(); fireEvent.click(screen.getByRole('button', { name: 'Подставить' }));
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить и отправить' }));
  await waitFor(() => expect(submitted).toMatchObject({ consents: { auto_decision: true } }));
});
it('неверный код очищается и ошибка сервера видна под полем', async () => {
  otp(); open();
  server.use(http.post('*/api/v1/applications/:id/submit', () => HttpResponse.json({ error: { code: 'OTP_INVALID', message: 'Неверный код. Попробуйте ещё раз.', details: {} } }, { status: 422 })));
  await consentAndCode(); fireEvent.click(screen.getByRole('button', { name: 'Подставить' }));
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить и отправить' }));
  await screen.findByText('Неверный код. Попробуйте ещё раз.');
  expect((screen.getByLabelText('Код из SMS') as HTMLInputElement).value).toBe('');
});
it('истечение кода открывает получение нового кода', async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
  otp(Date.now() + 1000); open(); await consentAndCode(); await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(screen.getByText('Код истёк')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Получить новый код' })).toBeTruthy();
});
it('бухгалтер передаёт заявку директору без согласий', async () => {
  const application = open('ooo_load_accountant');
  expect(screen.queryByRole('checkbox')).toBeNull();
  server.use(http.post('*/api/v1/applications/:id/request-signature', () => HttpResponse.json({ ...application, awaiting_signature: true, allowed_actions: [] })));
  fireEvent.click(screen.getByRole('button', { name: 'Отправить на подпись директору' }));
  expect(await screen.findByText('Отправлено на подпись — руководитель увидит заявку в своём списке')).toBeTruthy();
});
it('повторный просмотр переданной заявки сразу показывает ожидание', () => {
  open('ooo_load_accountant', true);
  expect(screen.getByText('Отправлено на подпись — руководитель увидит заявку в своём списке')).toBeTruthy();
  expect(screen.queryByRole('button')).toBeNull();
});
