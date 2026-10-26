import { MantineProvider } from '@mantine/core';
import { cleanup, render, screen } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SigningSection from './SigningSection';

type Application = ComponentProps<typeof SigningSection>['application'];

const application: Application = {
  id: 'application', number: 1, version: 1, company_id: 'company', state: 'SIGNING',
  stage: { index: 5, code: 'SIGNING', title: 'Подписание', what_happens: 'Подписание договора', what_to_do: null },
  timeline: [], product_code: 'EXPRESS', amount: 500000, term_months: 12,
  purpose: 'WORKING_CAPITAL', purpose_text: null, declared_revenue_year: 6000000,
  offer: {
    id: 'offer', version: 1, kind: 'APPROVED', status: 'ACCEPTED', product_code: 'EXPRESS',
    amount: 500000, term_months: 12, rate: 22, monthly_payment: 46700,
    expires_at: '2026-10-30T22:30:00Z', explanation: ['Стабильный оборот'], requested: null, counter_reason: null,
  },
  client_reason: null, info_request: null,
  parties: [
    { id: 'borrower', role: 'BORROWER_SIGNATORY', full_name: 'Иван Иванов', signed: false, is_me: true },
    { id: 'guarantor', role: 'GUARANTOR', full_name: 'Пётр Петров', signed: false, is_me: false },
  ],
  allowed_actions: ['SIGN'], awaiting_signature: false, objection: null,
  created_at: '2026-10-26T06:00:00Z', updated_at: '2026-10-26T06:00:00Z',
};

function section(value: Application) {
  return <MantineProvider><SigningSection application={value} onUpdate={vi.fn()} onReload={async () => {}} onMessage={vi.fn()} /></MantineProvider>;
}

afterEach(cleanup);

describe('Срок подписания', () => {
  it('в SIGNING показывает дату оферты по московскому времени и убирает её после всех подписей', () => {
    const { rerender } = render(section(application));
    expect(screen.getByText('Подписать нужно до 31.10.2026')).toBeTruthy();

    rerender(section({ ...application, parties: application.parties.map((party) => ({ ...party, signed: true })) }));
    expect(screen.queryByText(/Подписать нужно до/)).toBeNull();
  });

  it('оставляет срок, когда клиент подписал, но поручитель ещё не подписал', () => {
    render(section({ ...application, parties: application.parties.map((party) => ({ ...party, signed: party.is_me })) }));
    expect(screen.getByText('Подписать нужно до 31.10.2026')).toBeTruthy();
  });

  it.each(['SIGNED', 'OFFER_ISSUED', 'EXPIRED'] as const)('не показывает срок в состоянии %s', (state) => {
    render(section({ ...application, state }));
    expect(screen.queryByText(/Подписать нужно до/)).toBeNull();
  });

  it('не показывает срок без участников', () => {
    render(section({ ...application, parties: [] }));
    expect(screen.queryByText(/Подписать нужно до/)).toBeNull();
  });

  it('не показывает срок без оферты', () => {
    render(section({ ...application, offer: null }));
    expect(screen.queryByText(/Подписать нужно до/)).toBeNull();
  });
});
