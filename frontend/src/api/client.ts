import createClient from 'openapi-fetch';
import { notifications } from '@mantine/notifications';
import { getToken, setToken } from '../auth/session';
import type { components, paths } from './schema';

type ApiError = components['schemas']['ApiError'];

export function fieldErrors(error: ApiError | undefined): Record<string, string> {
  const fields = error?.error.details.fields;
  if (!fields || typeof fields !== 'object') return {};
  return Object.fromEntries(Object.entries(fields).filter((entry): entry is [string, string] => typeof entry[1] === 'string'));
}

function errorMessage(body: unknown): string | undefined {
  if (typeof body !== 'object' || body === null || !('error' in body)) return;
  const error = body.error;
  if (typeof error === 'object' && error !== null && 'message' in error && typeof error.message === 'string') return error.message;
}

// OpenAPI contains full paths; the client owns the /api/v1 prefix once.
type RelativePaths = {
  [Path in keyof paths as Path extends `/api/v1${infer Relative}`
    ? Relative
    : never]: paths[Path];
};

export const api = createClient<RelativePaths>({
  baseUrl: '/api/v1',
  fetch: (request) => globalThis.fetch(request),
});

api.use({
  onRequest({ request, schemaPath }) {
    const token = getToken();
    if (token && schemaPath !== '/auth/login') request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
  async onResponse({ response }) {
    if (response.status === 401) setToken(null);
    if (!response.ok) {
      const body: unknown = await response.clone().json().catch(() => null);
      notifications.show({ color: 'red', title: 'Не удалось выполнить действие', message: errorMessage(body) ?? 'Не удалось выполнить запрос. Попробуйте ещё раз.' });
    }
  },
  onError() {
    notifications.show({ color: 'red', message: 'Нет связи с сервером. Проверьте соединение и попробуйте ещё раз.' });
  },
});

