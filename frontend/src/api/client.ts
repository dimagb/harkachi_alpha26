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

// Calculator uses POST, but only reads an estimate like the GET queries.
function isAction(request: Request, schemaPath: string): boolean {
  return request.method !== 'GET' && request.method !== 'HEAD' && schemaPath !== '/calculator';
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
  async onResponse({ request, schemaPath, response }) {
    if (response.status === 401) setToken(null);
    if (!response.ok && isAction(request, schemaPath)) {
      const body: unknown = await response.clone().json().catch(() => null);
      const message = errorMessage(body) ?? 'Не удалось выполнить запрос. Попробуйте ещё раз.';
      notifications.show({ id: `api-error:${message}`, color: 'red', title: 'Не удалось выполнить действие', message });
    }
  },
  onError({ request, schemaPath, error }) {
    if (!isAction(request, schemaPath)) return;
    if (typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError') return;
    const message = 'Нет связи с сервером. Проверьте соединение и попробуйте ещё раз.';
    notifications.show({ id: `api-error:${message}`, color: 'red', message });
  },
});

