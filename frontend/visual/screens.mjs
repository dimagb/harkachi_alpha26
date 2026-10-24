import assert from 'node:assert/strict';
import console from 'node:console';
import process from 'node:process';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath, URL } from 'node:url';
import { chromium } from '@playwright/test';
import { createServer } from 'vite';
import { setupServer } from 'msw/node';

const check = process.argv.includes('--check');
const out = fileURLToPath(new URL('./out/', import.meta.url));
if (!check) await mkdir(out, { recursive: true });
// Use the project's MSW handlers in Node so Playwright can also intercept errors.
// A browser service worker would hide its responses from route.fulfill.
const vite = await createServer({
  define: { 'import.meta.env.VITE_USE_MSW': '"false"' },
  server: { host: '127.0.0.1', port: 0, open: false },
});
let browser;
let mocks;
try {
  const { createHandlers } = await vite.ssrLoadModule('/src/mocks/handlers.ts');
  mocks = setupServer(...createHandlers());
  mocks.listen({ onUnhandledFrame: 'bypass' });
  await vite.listen();
  const appUrl = vite.resolvedUrls.local[0].replace(/\/$/, '');
  browser = await chromium.launch(process.env.VISUAL_BROWSER ? { channel: process.env.VISUAL_BROWSER } : {});
  for (const width of [1440, 375]) {
    const context = await browser.newContext({ viewport: { width, height: 1100 }, deviceScaleFactor: 1, reducedMotion: 'reduce', serviceWorkers: 'block' });
    const failures = new Set();
    const requests = new Map();
    const issues = [];
    context.on('page', page => page.on('pageerror', error => issues.push(error.message)));
    await context.route('**/api/v1/**', async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      requests.set(path, (requests.get(path) ?? 0) + 1);
      if (failures.has(path)) {
        await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'Не удалось загрузить данные. Попробуйте ещё раз.', details: {} } }) });
        return;
      }
      const response = await globalThis.fetch(request.url(), { method: request.method(), headers: request.headers(), ...(request.postData() ? { body: request.postData() } : {}) });
      await route.fulfill({ status: response.status, headers: Object.fromEntries(response.headers), body: await response.text() });
    });
    const page = await context.newPage();
    async function capture(name) {
      await page.evaluate(() => globalThis.document.fonts.ready);
      await page.waitForTimeout(300);
      const dimensions = await page.evaluate(() => ({ width: globalThis.document.documentElement.scrollWidth, viewport: globalThis.innerWidth }));
      assert(dimensions.width <= dimensions.viewport, `${name}: горизонтальный скролл на ${width} px (${dimensions.width})`);
      if (['queue-error', 'journal-error', 'applications-error'].includes(name)) {
        assert.equal(await page.locator('.mantine-Notifications-root .mantine-Notification-root').count(), 0, `${name}: 0 уведомлений`);
      }
      if (!check) await page.screenshot({ path: `${out}/screens-${name}-${width}.png`, fullPage: true });
      console.log(`${name}: ${width} px, горизонтального скролла нет`);
    }
    async function login(name) {
      mocks.resetHandlers(...createHandlers());
      await page.goto(`${appUrl}/login`);
      await page.evaluate(() => globalThis.sessionStorage.clear());
      await page.reload();
      await page.getByLabel(/^Логин/).fill(name);
      await page.getByLabel(/^Пароль/).fill('demo2026');
      await page.getByRole('button', { name: 'Войти', exact: true }).click();
      await page.getByRole('heading', { name: name === 'underwriter' ? 'Очередь' : 'Мои заявки', exact: true }).waitFor();
    }

    await page.goto(`${appUrl}/login`);
    await page.getByRole('heading', { name: 'Вход', exact: true }).waitFor();
    await capture('login');
    const loginButton = page.getByRole('button', { name: 'Войти', exact: true });
    assert.equal(await loginButton.evaluate(element => globalThis.getComputedStyle(element).backgroundColor), await page.evaluate(() => globalThis.getComputedStyle(globalThis.document.documentElement).getPropertyValue('--cc-signal').trim().toUpperCase()).then(async token => {
      return page.evaluate(value => { const element = globalThis.document.createElement('span'); element.style.color = value; globalThis.document.body.append(element); const color = globalThis.getComputedStyle(element).color; element.remove(); return color; }, token);
    }), 'Войти: основной сигнальный цвет');

    await login('ip_good');
    await page.getByRole('link', { name: /№ 1001/ }).waitFor();
    await capture('applications');
    if (width === 375) {
      const header = page.locator('header').first();
      assert((await header.boundingBox()).height <= 56, 'Высота мобильной шапки ≤ 56 px');
      await page.getByRole('button', { name: 'Открыть меню' }).click();
      const menu = page.getByRole('dialog', { name: 'Меню кабинета' });
      await menu.getByRole('link', { name: 'Мои заявки', exact: true }).waitFor();
      await menu.getByRole('button', { name: 'Выйти', exact: true }).waitFor();
      await capture('mobile-menu');
      await menu.getByRole('link', { name: 'Получить финансирование', exact: true }).click();
      await menu.waitFor({ state: 'hidden' });
      await page.getByRole('heading', { name: 'Зачем нужны деньги?', exact: true }).waitFor();
      await page.getByRole('button', { name: 'Открыть меню' }).click();
      await menu.waitFor();
      await page.goBack();
      await page.getByRole('heading', { name: 'Мои заявки', exact: true }).waitFor();
      await menu.waitFor({ state: 'hidden' });
      await page.goForward();
      await page.getByRole('heading', { name: 'Зачем нужны деньги?', exact: true }).waitFor();
      await page.waitForTimeout(300);
      assert.equal(await menu.count(), 0, 'История браузера не открывает меню повторно');
    } else await page.goto(`${appUrl}/app/applications/new`);
    await page.getByRole('heading', { name: 'Зачем нужны деньги?', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Кассовый разрыв', exact: true }).click();
    await page.getByRole('region', { name: 'Экспресс-кредит', exact: true }).waitFor();
    await capture('selection');
    await page.getByRole('region', { name: 'Экспресс-кредит', exact: true }).getByRole('button', { name: 'Выбрать', exact: true }).click();
    await page.getByText(/Платёж в месяц ≈/).waitFor();
    await capture('form');

    failures.add('/api/v1/applications');
    await page.goto(`${appUrl}/app`);
    await page.getByRole('button', { name: 'Повторить', exact: true }).waitFor();
    await capture('applications-error');
    const failedApplications = requests.get('/api/v1/applications');
    failures.clear();
    await page.getByRole('button', { name: 'Повторить', exact: true }).click();
    await page.getByRole('link', { name: /№ 1001/ }).waitFor();
    assert(requests.get('/api/v1/applications') > failedApplications, 'Повторить запрашивает заявки заново');

    await login('ooo_gap');
    await page.getByText('Заявок пока нет', { exact: true }).waitFor();
    await page.getByRole('main').getByRole('link', { name: 'Получить финансирование', exact: true }).waitFor();
    await capture('applications-empty');

    await login('underwriter');
    await page.getByRole('table', { name: 'Очередь заявок' }).waitFor();
    await capture('queue');
    failures.add('/api/v1/underwriting/queue');
    const beforeQueueError = requests.get('/api/v1/underwriting/queue') ?? 0;
    await page.reload();
    await page.getByRole('button', { name: 'Повторить', exact: true }).waitFor();
    assert.equal(requests.get('/api/v1/underwriting/queue') - beforeQueueError, 2, 'Очередь: один автоматический повтор');
    await capture('queue-error');
    failures.clear();
    await page.getByRole('button', { name: 'Повторить', exact: true }).click();
    await page.getByRole('table', { name: 'Очередь заявок' }).waitFor();

    await page.goto(`${appUrl}/bank/journal`);
    await page.getByRole('table', { name: 'Заявки банка' }).waitFor();
    await capture('journal');
    failures.add('/api/v1/bank/applications');
    const beforeJournalError = requests.get('/api/v1/bank/applications') ?? 0;
    await page.reload();
    await page.getByRole('button', { name: 'Повторить', exact: true }).waitFor();
    assert.equal(requests.get('/api/v1/bank/applications') - beforeJournalError, 2, 'Журнал: один автоматический повтор');
    await capture('journal-error');
    const failedJournal = requests.get('/api/v1/bank/applications');
    failures.clear();
    await page.getByRole('button', { name: 'Повторить', exact: true }).click();
    await page.getByRole('table', { name: 'Заявки банка' }).waitFor();
    assert(requests.get('/api/v1/bank/applications') > failedJournal, 'Повторить запрашивает журнал заново');
    assert.deepEqual(issues, [], 'Нет ошибок JavaScript');
    await context.close();
  }
  console.log(`F-10: все проверки пройдены${check ? ', без скриншотов' : ''}`);
} finally {
  mocks?.close();
  await browser?.close();
  await vite.close();
}
