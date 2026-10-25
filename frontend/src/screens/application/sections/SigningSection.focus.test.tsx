import { MantineProvider } from '@mantine/core';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { applications } from '../../../mocks/fixtures';
import StatusPanel from '../StatusPanel';
import SigningSection from './SigningSection';

const server = setupServer(http.post('*/api/v1/applications/:id/otp', () => HttpResponse.json({
  otp_id: 'otp-focus', demo_code: '123456', expires_at: new Date(Date.now() + 300000).toISOString(),
})));
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(cleanup);
afterAll(() => server.close());

it.each(['панели', 'раздела'])('кнопка «Подписать договор» из %s переводит фокус в поле кода', async (entry) => {
  const application = { ...applications[0]!, state: 'SIGNING' as const, allowed_actions: ['SIGN' as const], parties: [
    { id: 'borrower', role: 'BORROWER_SIGNATORY' as const, full_name: 'Смирнова Анна Викторовна', signed: false, is_me: true },
  ] };
  render(<MantineProvider env="test"><MemoryRouter>
    <StatusPanel application={application} status="current" />
    <SigningSection application={application} onUpdate={() => {}} onReload={async () => {}} onMessage={() => {}} />
  </MemoryRouter></MantineProvider>);
  if (entry === 'панели') {
    fireEvent.click(within(screen.getByRole('region', { name: 'Что происходит с заявкой' })).getByRole('link', { name: 'Подписать договор' }));
    const signingButton = within(screen.getByRole('region', { name: 'Подписание' })).getByRole('button', { name: 'Подписать договор' });
    expect(document.activeElement).toBe(signingButton);
    fireEvent.click(signingButton);
  } else {
    fireEvent.click(within(screen.getByRole('region', { name: 'Подписание' })).getByRole('button', { name: 'Подписать договор' }));
  }
  const input = await screen.findByLabelText('Код из СМС');
  await waitFor(() => expect(document.activeElement).toBe(input));
  fireEvent.click(within(screen.getByRole('region', { name: 'Что происходит с заявкой' })).getByRole('link', { name: 'Подписать договор' }));
  expect(document.activeElement).toBe(input);
});
