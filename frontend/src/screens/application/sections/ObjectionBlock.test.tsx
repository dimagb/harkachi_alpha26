import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { applications } from '../../../mocks/fixtures';
import { theme } from '../../../theme';
import ObjectionBlock from './ObjectionBlock';
import css from './ObjectionBlock.module.css';

afterEach(cleanup);

it.each(['PENDING', 'RESOLVED'] as const)('плашка пересмотра %s использует inline-оформление внутри карточки', (status) => {
  const application = { ...applications[0]!, objection: { status, created_at: '2026-10-24T09:00:00Z', outcome_text: 'Решение проверено специалистом' } };
  const client = new QueryClient();
  const view = (inline: boolean) => <MantineProvider theme={theme} env="test"><QueryClientProvider client={client}><ObjectionBlock application={application} inline={inline} onUpdate={() => {}} onReload={() => Promise.resolve()} onMessage={() => {}} /></QueryClientProvider></MantineProvider>;
  const { rerender } = render(view(true));
  const banner = screen.getByRole('status', { name: 'Пересмотр решения' });
  expect(banner.classList.contains(css.inline!)).toBe(true);
  expect(banner.textContent).toBe(status === 'PENDING' ? 'Ваше обращение рассматривает специалист банка' : 'Решение проверено специалистом');
  rerender(view(false));
  expect(screen.getByRole('status', { name: 'Пересмотр решения' }).classList.contains(css.inline!)).toBe(false);
});
