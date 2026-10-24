import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterAll, afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { createBankHandlers } from '../../mocks/bank/handlers';
import { bankApplications, borderDecision } from '../../mocks/bank/fixtures';
import { theme } from '../../theme';
import ProtocolPrint from './ProtocolPrint';

const server = setupServer();
let client: QueryClient;
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
beforeEach(() => { sessionStorage.setItem('access_token', 'demo:underwriter'); server.resetHandlers(...createBankHandlers()); });
afterEach(() => { cleanup(); client.clear(); sessionStorage.clear(); vi.restoreAllMocks(); });
function open() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<MantineProvider theme={theme} env="test"><QueryClientProvider client={client}><MemoryRouter initialEntries={['/bank/applications/ooo_border/protocol']}><Routes><Route path="/bank/applications/:id/protocol" element={<ProtocolPrint />} /></Routes></MemoryRouter></QueryClientProvider></MantineProvider>);
}

it('печатает полный протокол ooo_border: 12 признаков, итог 54, рекомендация, источники и история без меню', async () => {
  const print = vi.spyOn(window, 'print').mockImplementation(() => {});
  open(); await screen.findByRole('heading', { name: 'Протокол решения по заявке № 1047' });
  expect(screen.getByText(/7705123452/)).toBeTruthy();
  expect(within(screen.getByRole('table', { name: 'Факторы оценки' })).getAllByRole('row')).toHaveLength(13);
  expect(screen.getByText('Итого 54 / 100 · Класс C')).toBeTruthy();
  expect(screen.getByRole('heading', { name: 'Рекомендация системы' })).toBeTruthy();
  expect(screen.getByText('Оценка 54 из 100, класс C')).toBeTruthy();
  expect(within(screen.getByRole('table', { name: 'Сведения источников' })).getAllByRole('row')).toHaveLength(4);
  expect(screen.queryByRole('navigation')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Печать' })); expect(print).toHaveBeenCalledOnce();
});

it('выводит все решения новыми первыми, полный расчёт, правила, внутренние причины и комментарий специалиста', async () => {
  const app = structuredClone(bankApplications[0]!);
  app.decisions = [{ ...borderDecision, id: 'manual', kind: 'MANUAL', made_by: 'Иван Петров', comment: 'Документы проверены специалистом', created_at: '2026-10-24T10:00:00Z' }, { ...borderDecision, policy: { ...borderDecision.policy!, steps: ['Проверка доступного платежа'] }, rules_fired: [{ code: 'POLICY', title: 'Проверка лимита', value: '1 000 000 ₽', threshold: '1 825 000 ₽', effect: 'POLICY' }] }];
  server.use(http.get('*/api/v1/underwriting/applications/ooo_border', () => HttpResponse.json(app)));
  open(); await screen.findByText(/Документы проверены специалистом/);
  const decisions = screen.getAllByRole('region', { name: /решение/ });
  expect(decisions[0]!.textContent).toContain('Иван Петров');
  expect(decisions[1]!.textContent).toContain('Проверка лимита');
  expect(screen.getByText('Проверка доступного платежа')).toBeTruthy();
  expect(screen.getByText('Пограничная оценка: требуется решение специалиста.')).toBeTruthy();
  expect(screen.getByText('Запрошенный платёж')).toBeTruthy();
  expect(screen.getByText('Что изменило бы решение')).toBeTruthy();
});

it('даёт повторить запрос при ошибке', async () => {
  server.use(http.get('*/api/v1/underwriting/applications/ooo_border', () => new HttpResponse(null, { status: 500 })));
  open(); await screen.findByRole('button', { name: 'Повторить' });
  server.resetHandlers(...createBankHandlers());
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
  expect(await screen.findByRole('heading', { name: 'Протокол решения по заявке № 1047' })).toBeTruthy();
});
