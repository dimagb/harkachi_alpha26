export async function startMocks() {
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MSW === 'true') {
    const { worker } = await import('./browser');
    await worker.start({ onUnhandledFrame: 'bypass' });
  }
}
