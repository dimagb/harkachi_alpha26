import createClient from 'openapi-fetch';
import type { paths } from './schema';

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

