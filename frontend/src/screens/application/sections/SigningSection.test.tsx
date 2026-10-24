import { MantineProvider } from '@mantine/core';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { useState } from 'react';
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest';
import type { components } from '../../../api/schema';
import { setToken } from '../../../auth/session';
import { applications } from '../../../mocks/fixtures';
import SigningSection from './SigningSection';

type Application = components['schemas']['ApplicationClient'];
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterAll(() => server.close());
afterEach(() => { cleanup(); server.resetHandlers(); setToken(null); vi.useRealTimers(); });
function open(others = false, state: Application['state'] = 'SIGNING') {
  const base = applications[1]!;
  const initial: Application = { ...base, state, offer: { ...base.offer!, status: 'ACCEPTED' }, allowed_actions: ['SIGN'], parties: [
    { id: 'borrower', role: 'BORROWER_SIGNATORY', full_name: 'Петров Илья Игоревич', signed: false, is_me: true },
    { id: 'guarantor', role: 'GUARANTOR', full_name: 'Петров Илья Игоревич', signed: false, is_me: !others },
  ] };
  setToken('demo:ooo_load');
  const calls: unknown[] = [];
  server.use(http.post('*/api/v1/applications/:id/otp', async ({ request }) => {
    calls.push(await request.json()); return HttpResponse.json({ otp_id: 'otp-1', demo_code: '123456', expires_at: new Date(Date.now() + 300000).toISOString() });
  }));
  function Host() {
    const [application, setApplication] = useState(initial);
    return <SigningSection application={application} onUpdate={setApplication} onReload={async () => {}} onMessage={() => {}} />;
  }
  render(<MantineProvider env="test"><Host /></MantineProvider>);
  return { initial, calls };
}
async function sign(name: string) {
  fireEvent.click(screen.getByRole('button', { name }));
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Получить код' }));
  fireEvent.click(screen.getByRole('button', { name: 'Получить код' }));
  await screen.findByText('Демо-режим: код 123456');
  expect(document.activeElement).toBe(screen.getByLabelText('Код из SMS'));
  fireEvent.click(screen.getByRole('button', { name: 'Подставить' }));
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить подпись' }));
}
it('директор подписывает договор и поручительство по очереди, с разными purpose и party_id', async () => {
  const { initial, calls } = open();
  expect(screen.getAllByText('это вы')).toHaveLength(2);
  expect(screen.queryByRole('button', { name: 'Подписать поручительство' })).toBeNull();
  let current = initial; const bodies: unknown[] = [];
  server.use(http.post('*/api/v1/applications/:id/sign', async ({ request }) => {
    const body = await request.json() as { party_id: string }; bodies.push(body);
    const parties = current.parties.map((p) => p.id === body.party_id ? { ...p, signed: true } : p);
    current = { ...current, parties, state: parties.every((p) => p.signed) ? 'SIGNED' : 'SIGNING' };
    return HttpResponse.json(current);
  }));
  await sign('Подписать договор');
  await screen.findByRole('button', { name: 'Подписать поручительство' });
  expect(screen.getByText(/Вместе с поручительством вы подписываете согласия/)).toBeTruthy();
  await sign('Подписать поручительство');
  await screen.findByText('Договор подписан, готовим выдачу');
  expect(calls).toEqual([{ purpose: 'OFFER', party_id: 'borrower' }, { purpose: 'GUARANTEE', party_id: 'guarantor' }]);
  expect(bodies).toEqual([{ otp_id: 'otp-1', code: '123456', party_id: 'borrower' }, { otp_id: 'otp-1', code: '123456', party_id: 'guarantor' }]);
});
it('501 показывает понятную ошибку и оставляет возможность повторить', async () => {
  open(); server.use(http.post('*/api/v1/applications/:id/sign', () => HttpResponse.json({ error: { code: 'NOT_IMPLEMENTED', message: 'Недоступно', details: {} } }, { status: 501 })));
  await sign('Подписать договор');
  expect(await screen.findByText('Подписание пока недоступно, попробуйте позже')).toBeTruthy();
});
it('не подписывает чужую роль и объясняет ожидание', async () => {
  const { initial } = open(true);
  server.use(http.post('*/api/v1/applications/:id/sign', () => HttpResponse.json({ ...initial, parties: initial.parties.map((p) => p.is_me ? { ...p, signed: true } : p), allowed_actions: [] })));
  await sign('Подписать договор');
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Подписать договор' })).toBeNull());
  expect(screen.getByText('Ждём подписи остальных участников')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Подписать поручительство' })).toBeNull();
});
it('SIGNED показывает подготовку выдачи без кнопок подписи', async () => {
  await act(async () => { open(false, 'SIGNED'); });
  expect(screen.getByText('Договор подписан, готовим выдачу')).toBeTruthy();
  expect(screen.queryByRole('button')).toBeNull();
});
