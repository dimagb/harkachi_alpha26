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
  const { applications, applicationScenarios, accounts } = await vite.ssrLoadModule('/src/mocks/fixtures.ts');
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
      if (name !== 'login' && name !== 'mobile-menu') {
        const main = page.getByRole('main');
        const surface = await main.evaluate(element => {
          let node = element;
          while (node) {
            const background = globalThis.getComputedStyle(node).backgroundColor;
            if (background !== 'rgba(0, 0, 0, 0)') return background;
            node = node.parentElement;
          }
        });
        assert.equal(surface, 'rgb(242, 243, 245)', `${name}: серая подложка раздела`);
        const logo = page.getByRole('img', { name: 'Альфа-Банк', exact: true });
        const logoSize = await logo.boundingBox();
        assert(logoSize.height >= 24 && logoSize.height <= 28, `${name}: высота логотипа 24–28 px`);
        assert(await logo.evaluate(element => element.complete && element.naturalWidth > 0), `${name}: официальный логотип загружен`);
        await page.getByRole('contentinfo').getByText(/Данные синтетические/).waitFor();
        const cards = main.locator(page.url().includes('/bank/')
          ? '[class*="tableScroll"], [class*="section_"], [class*="stages_"], [class*="factors_"], [class*="formSection_"], [class*="protocol_"]'
          : '[class*="card_"]').filter({ visible: true });
        for (const element of await cards.all()) {
          const style = await element.evaluate(node => {
            const computed = globalThis.getComputedStyle(node);
            return { background: computed.backgroundColor, radius: computed.borderTopLeftRadius };
          });
          const label = await element.getAttribute('class');
          assert.equal(style.background, 'rgb(255, 255, 255)', `${name}: белая карточка ${label}`);
          assert.equal(style.radius, width === 375 ? '16px' : '24px', `${name}: скругление карточки ${label}`);
        }
        const faintOnGray = await main.evaluate(element => [...element.querySelectorAll('*')].filter(node => {
          if (![...node.childNodes].some(child => child.nodeType === 3 && child.textContent.trim())) return false;
          if (!node.getBoundingClientRect().width || globalThis.getComputedStyle(node).color !== 'rgb(106, 114, 128)') return false;
          let parent = node;
          while (parent) {
            const background = globalThis.getComputedStyle(parent).backgroundColor;
            if (background !== 'rgba(0, 0, 0, 0)') return background === 'rgb(242, 243, 245)';
            parent = parent.parentElement;
          }
          return false;
        }).map(node => node.textContent.trim()));
        assert.deepEqual(faintOnGray, [], `${name}: --cc-ink-3 используется только на белом`);
      }
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
    await login('ip_bad');
    await page.goto(`${appUrl}/app/applications/30000000-0000-4000-8000-000000000201`);
    const reason = page.getByRole('region', { name: 'Причина отказа' });
    await reason.waitFor();
    if (width === 1440) {
      await page.getByRole('contentinfo').scrollIntoViewIfNeeded();
      assert(await page.evaluate(() => globalThis.scrollY > 0), 'Длинная карточка действительно прокручена');
      const navbar = page.getByRole('navigation', { name: 'Главная навигация', exact: true });
      assert(await navbar.evaluate(element => {
        const box = element.getBoundingClientRect();
        const style = globalThis.getComputedStyle(element);
        return style.position === 'fixed' && Math.abs(box.top) <= 1 && Math.abs(box.bottom - globalThis.innerHeight) <= 1 && style.backgroundColor === 'rgb(255, 255, 255)';
      }), 'Левая панель закреплена и занимает всё окно после прокрутки');
      const navigationLink = await navbar.getByRole('link', { name: 'Мои заявки', exact: true }).boundingBox();
      assert(navigationLink && navigationLink.y >= 0 && navigationLink.y + navigationLink.height <= 1100, 'Ссылки навигации остаются в окне после прокрутки');
    } else {
      assert.equal(await page.getByRole('navigation', { name: 'Главная навигация', exact: true }).count(), 0, '375 px: остаётся бургер без боковой панели');
    }
    const objection = reason.getByRole('region', { name: 'Пересмотр решения' });
    await objection.getByRole('button', { name: 'Попросить пересмотр', exact: true }).waitFor();
    const objectionStyle = await objection.evaluate(element => {
      const style = globalThis.getComputedStyle(element);
      return { border: style.borderTopColor, width: style.borderTopWidth, background: style.backgroundColor };
    });
    assert.deepEqual(objectionStyle, { border: 'rgb(228, 230, 234)', width: '1px', background: 'rgba(0, 0, 0, 0)' }, 'Пересмотр: нижняя строка причины через --cc-line');
    const newApplication = page.getByRole('link', { name: 'Подать новую заявку', exact: true });
    assert.equal(await newApplication.evaluate(element => globalThis.getComputedStyle(element).backgroundColor), 'rgb(255, 255, 255)', 'Отказ с датой повтора: новая заявка — белая вторичная кнопка');
    const back = page.getByRole('link', { name: 'Вернуться к заявкам', exact: true });
    assert(await back.evaluate(element => !!element.closest('section[class*="card_"]')), 'Возврат к заявкам внутри белой карточки');
    await capture('decline');
    await login('ip_good');
    if (width === 375) {
      for (const name of ['ip_good', 'ooo_load', 'ip_bad', 'ooo_aml']) {
        if (name !== 'ip_good') await login(name);
        const companyIds = accounts[name].companies.map(item => item.company.id);
        const cards = [...applications, ...applicationScenarios].filter(item => companyIds.includes(item.company_id));
        for (const application of cards) {
          await page.goto(`${appUrl}/app/applications/${application.id}`);
          await page.getByRole('region', { name: 'Что происходит с заявкой' }).waitFor();
          const label = `card-${application.state.toLowerCase()}-${application.number}`;
          await capture(label);
          const overflowing = await page.getByRole('main').locator('h1, h2, h3, [class*="badge"], [class*="heading"]').evaluateAll(elements => elements.filter(element => {
            const box = element.getBoundingClientRect();
            return box.width > 1 && box.height > 1 && (box.right > globalThis.innerWidth + 1 || box.left < -1 || element.scrollWidth > box.width + 1 || element.scrollHeight > box.height + 1);
          }).map(element => element.textContent));
          assert.deepEqual(overflowing, [], `${label}: заголовки и бейджи помещаются в карточку`);
          if (application.number === 1301 || application.number === 1304) {
            if (application.number === 1301) {
              await page.getByRole('checkbox', { name: 'Согласен: обработка персональных данных' }).check();
              await page.getByRole('checkbox', { name: 'Согласен: запрос кредитной истории' }).check();
            }
            await page.getByRole('button', { name: application.number === 1301 ? 'Подписать и отправить' : 'Подписать договор', exact: true }).click();
            const input = page.getByLabel('Код из СМС');
            await input.waitFor();
            assert(await input.evaluate(element => element === globalThis.document.activeElement), `${label}: фокус в поле кода`);
            const box = await input.boundingBox();
            assert(box.y >= 0 && box.y + box.height <= 1100, `${label}: поле кода в видимой области`);
          }
        }
      }
      await login('ip_good');
    }
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
    const purposeStyle = await page.getByRole('button', { name: 'Кассовый разрыв', exact: true }).evaluate(element => {
      const style = globalThis.getComputedStyle(element);
      return { background: style.backgroundColor, border: style.borderTopColor, selected: element.getAttribute('aria-pressed') };
    });
    assert.deepEqual(purposeStyle, { background: 'rgb(255, 255, 255)', border: 'rgb(31, 35, 41)', selected: 'true' }, 'Цель: белая карточка с чёрной рамкой выбранного варианта');
    await page.getByRole('region', { name: 'Экспресс-кредит', exact: true }).getByRole('button', { name: 'Выбрать', exact: true }).click();
    await page.getByText(/Платёж в месяц ≈/).waitFor();
    await capture('form');
    assert.equal(await page.locator('.mantine-NumberInput-controls').count(), 0, 'У суммы и выручки нет стрелок ±1');
    assert.equal(await page.getByRole('combobox', { name: 'Срок, мес.' }).count(), 1, 'Больше шести сроков: выпадающий список');
    await page.getByRole('button', { name: 'Назад к выбору продукта', exact: true }).click();
    await page.getByRole('region', { name: 'Овердрафт', exact: true }).getByRole('button', { name: 'Выбрать', exact: true }).click();
    const term = page.getByRole('radio', { name: '12', exact: true });
    assert(await term.isChecked() && await term.isDisabled(), 'Овердрафт: срок 12 выбран и заблокирован');
    const termStyle = await page.locator('.mantine-Chip-label').evaluate(element => {
      const style = globalThis.getComputedStyle(element);
      return { background: style.backgroundColor, color: style.color, radius: style.borderRadius };
    });
    assert.deepEqual(termStyle, { background: 'rgb(31, 35, 41)', color: 'rgb(255, 255, 255)', radius: '999px' }, 'Срок: чёрная таблетка с белым текстом');

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
    await page.getByRole('table', { name: 'Очередь заявок' }).getByRole('link').first().click();
    await page.getByRole('region', { name: 'Факторы оценки' }).waitFor();
    const factor = page.locator('button[class*="factorRow"]').first();
    await factor.hover();
    await capture('underwriter');
    const padding = await factor.evaluate(element => {
      const style = globalThis.getComputedStyle(element);
      return { left: parseFloat(style.paddingLeft), right: parseFloat(style.paddingRight) };
    });
    assert(padding.right >= padding.left, 'У строки фактора отступ справа не меньше левого');
    await page.goBack();
    await page.getByRole('table', { name: 'Очередь заявок' }).waitFor();
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
  console.log(`F-10/F-11/F-12: все проверки пройдены${check ? ', без скриншотов' : ''}`);
} finally {
  mocks?.close();
  await browser?.close();
  await vite.close();
}
