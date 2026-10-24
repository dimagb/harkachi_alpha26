import { MantineProvider } from '@mantine/core';
import { Notifications, notifications } from '@mantine/notifications';
import { act, cleanup, render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { api } from './client';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
afterEach(() => { cleanup(); notifications.clean(); server.resetHandlers(); });
function openNotifications() {
  render(<MantineProvider env="test"><Notifications autoClose={false} /></MantineProvider>);
}
const failure = () => HttpResponse.json({ error: { code: 'INTERNAL_ERROR', message: 'Данные недоступны', details: {} } }, { status: 500 });

it('ошибки чтения, включая POST расчёта, не показывают уведомлений', async () => {
  server.use(http.get('*/api/v1/underwriting/queue', failure), http.post('*/api/v1/calculator', failure));
  openNotifications();
  await act(async () => {
    await api.GET('/underwriting/queue');
    await api.GET('/underwriting/queue');
    await api.POST('/calculator', { body: { product_code: 'EXPRESS', amount: 500000, term_months: 12 } });
  });
  expect(screen.queryByText('Данные недоступны')).toBeNull();
  expect(document.querySelectorAll('.mantine-Notification-root')).toHaveLength(0);
});

it('два одинаковых 409 действия дают одно уведомление с error.message', async () => {
  server.use(http.post('*/api/v1/applications/:id/offer/accept', () => HttpResponse.json({ error: { code: 'CONFLICT_VERSION', message: 'Условия изменились', details: {} } }, { status: 409 })));
  openNotifications();
  await act(async () => {
    await api.POST('/applications/{id}/offer/accept', { params: { path: { id: 'test' } }, body: { offer_version: 1 } });
    await api.POST('/applications/{id}/offer/accept', { params: { path: { id: 'test' } }, body: { offer_version: 1 } });
  });
  expect(screen.getAllByText('Условия изменились')).toHaveLength(1);
  expect(document.querySelectorAll('.mantine-Notification-root')).toHaveLength(1);
});

it('ошибка связи при чтении не даёт уведомлений, у действий одинаковая ошибка одна', async () => {
  server.use(http.get('*/api/v1/products', () => HttpResponse.error()), http.post('*/api/v1/calculator', () => HttpResponse.error()), http.post('*/api/v1/applications/:id/offer/accept', () => HttpResponse.error()));
  openNotifications();
  await act(async () => {
    await expect(api.GET('/products')).rejects.toThrow('Нет связи с сервером. Проверьте соединение и попробуйте ещё раз.');
    await expect(api.POST('/calculator', { body: { product_code: 'EXPRESS', amount: 500000, term_months: 12 } })).rejects.toThrow('Нет связи с сервером. Проверьте соединение и попробуйте ещё раз.');
  });
  expect(document.querySelectorAll('.mantine-Notification-root')).toHaveLength(0);
  await act(async () => {
    for (let attempt = 0; attempt < 2; attempt++) {
      await expect(api.POST('/applications/{id}/offer/accept', { params: { path: { id: 'test' } }, body: { offer_version: 1 } })).rejects.toThrow();
    }
  });
  expect(screen.getAllByText('Нет связи с сервером. Проверьте соединение и попробуйте ещё раз.')).toHaveLength(1);
});
