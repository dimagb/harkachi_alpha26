import { MantineProvider } from '@mantine/core';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, it } from 'vitest';
import { applications } from '../../../mocks/fixtures';
import DisbursedSection from './DisbursedSection';

afterEach(cleanup);
function open(overdraft = false) {
  const base = applications[0]!;
  render(<MantineProvider env="test"><MemoryRouter><DisbursedSection application={{ ...base, state: 'DISBURSED', offer: { ...base.offer!, product_code: overdraft ? 'OVERDRAFT' : 'EXPRESS' }, allowed_actions: ['NEW_APPLICATION'], timeline: base.timeline.map((step) => ({ ...step, status: 'done', at: step.stage_code === 'DISBURSEMENT' ? '2026-10-24T09:00:00Z' : step.at })) }} /></MemoryRouter></MantineProvider>);
}
it('показывает выдачу, дату из ленты и 24 платежа с нулевым остатком', () => {
  open(); expect(screen.getByRole('heading', { name: 'Деньги зачислены на счёт' })).toBeTruthy();
  expect(screen.getByText('24.10.2026')).toBeTruthy();
  const table = screen.getByRole('table', { name: 'График платежей (расчётный)' });
  const rows = within(table).getAllByRole('row'); expect(rows).toHaveLength(25);
  expect(within(rows[1]!).getAllByRole('cell')[1]!.textContent).toBe('24.11.2026');
  expect(within(rows.at(-1)!).getAllByRole('cell').at(-1)!.textContent?.replace(/\s/g, ' ')).toBe('0 ₽');
  expect(screen.getByRole('link', { name: 'Подать новую заявку' }).getAttribute('href')).toBe('/app/applications/new');
});
it('овердрафт показывает лимит вместо графика', () => {
  open(true); expect(screen.queryByRole('table')).toBeNull();
  expect(screen.getByText(/Лимит открыт:/).textContent?.replace(/\s/g, ' ')).toBe('Лимит открыт: 1 500 000 ₽. Проценты — только за использованные дни');
});
