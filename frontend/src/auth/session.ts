const tokenKey = 'access_token';
const sessionEvent = 'credit-cabinet:session';

export function getToken() {
  return sessionStorage.getItem(tokenKey);
}

export function setToken(token: string | null) {
  if (token) sessionStorage.setItem(tokenKey, token);
  else {
    try { sessionStorage.removeItem(tokenKey); } catch { /* Хранилище может быть недоступно. */ }
    try {
      for (let index = sessionStorage.length - 1; index >= 0; index--) {
        const key = sessionStorage.key(index);
        if (key?.startsWith('application-form:')) {
          try { sessionStorage.removeItem(key); } catch { /* Продолжаем очистку остальных черновиков. */ }
        }
      }
    } catch { /* Выход доступен без хранилища. */ }
  }
  window.dispatchEvent(new Event(sessionEvent));
}

export function subscribeSession(listener: () => void) {
  window.addEventListener(sessionEvent, listener);
  return () => window.removeEventListener(sessionEvent, listener);
}
