import { afterEach, expect, it, vi } from 'vitest';
import { getToken, setToken, subscribeSession } from './session';

afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });

it('выход удаляет все черновики и последний выбор, сохраняя остальные данные вкладки', () => {
  setToken('token');
  sessionStorage.setItem('application-form:user:company:EXPRESS', '{}');
  sessionStorage.setItem('application-form:last:user:company', '{}');
  sessionStorage.setItem('application-form:another-user:company:OVERDRAFT', '{}');
  sessionStorage.setItem('unrelated', 'keep');
  let events = 0;
  const unsubscribe = subscribeSession(() => { events++; });
  try {
    setToken(null);
    expect(getToken()).toBeNull();
    expect(Object.keys(sessionStorage)).toEqual(['unrelated']);
    expect(sessionStorage.getItem('unrelated')).toBe('keep');
    expect(events).toBe(1);
  } finally { unsubscribe(); }
});

it('сохранение токена оставляет черновики для перезагрузки', () => {
  sessionStorage.setItem('application-form:user:company:EXPRESS', 'draft');
  setToken('token');
  expect(getToken()).toBe('token');
  expect(sessionStorage.getItem('application-form:user:company:EXPRESS')).toBe('draft');
});

it.each(['removeItem', 'key', 'length'] as const)('выход игнорирует ошибку хранилища %s и уведомляет подписчиков', (method) => {
  setToken('token');
  sessionStorage.setItem('application-form:user:company:EXPRESS', '{}');
  if (method === 'length') vi.spyOn(Storage.prototype, 'length', 'get').mockImplementation(() => { throw new Error('Storage unavailable'); });
  else vi.spyOn(Storage.prototype, method).mockImplementation(() => { throw new Error('Storage unavailable'); });
  let events = 0;
  const unsubscribe = subscribeSession(() => { events++; });
  try {
    expect(() => setToken(null)).not.toThrow();
    expect(events).toBe(1);
  } finally { unsubscribe(); }
});
