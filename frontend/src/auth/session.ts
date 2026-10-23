const tokenKey = 'access_token';
const sessionEvent = 'credit-cabinet:session';

export function getToken() {
  return sessionStorage.getItem(tokenKey);
}

export function setToken(token: string | null) {
  if (token) sessionStorage.setItem(tokenKey, token);
  else sessionStorage.removeItem(tokenKey);
  window.dispatchEvent(new Event(sessionEvent));
}

export function subscribeSession(listener: () => void) {
  window.addEventListener(sessionEvent, listener);
  return () => window.removeEventListener(sessionEvent, listener);
}
