import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';
import { theme } from './theme';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('renders App and requests the health URL with a single API prefix', async () => {
  const fetchMock = vi.fn(async (request: Request) => {
    expect(new URL(request.url).pathname).toBe('/api/v1/health');
    return new Response(JSON.stringify({ status: 'ok' }), {
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <MantineProvider theme={theme} env="test">
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </MantineProvider>,
  );
  expect(screen.getByRole('heading').textContent).toBe('Кредитный кабинет — каркас');
  expect((await screen.findByText('API: ok')).textContent).toBe('API: ok');
  expect(fetchMock).toHaveBeenCalledOnce();
  queryClient.clear();
});

