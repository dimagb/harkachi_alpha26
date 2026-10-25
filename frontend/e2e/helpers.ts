import { test as base, expect, type BrowserContext, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import process from 'node:process';

export type Offer = { amount: number; term_months: number; rate: number; monthly_payment: number };
type Expected = { offer?: Offer; after_info?: { offer: Offer }; recommendation?: { offer: Offer; score: number; grade: string; points: Record<string, number> } };
export type Persona = {
  code: string;
  kind: string;
  name: string;
  demo: {
    app: { product: string; amount: number; term: number; purpose: string; declared_revenue_year: number };
    consents: { pdn: boolean; bki: boolean; auto_decision: boolean };
    info_response?: { value: number; comment: string }[];
    expected: Expected;
  };
};
const data = JSON.parse(readFileSync(new URL('../../contracts/personas.json', import.meta.url), 'utf8')) as { personas: Persona[] };
export function persona(code: string): Persona {
  const found = data.personas.find(item => item.code === code);
  if (!found) throw new Error(`Нет golden-персонажа ${code}`);
  return found;
}

type Expected4xx = { method: string; path: string; status: number };
type Step = (name: string, body: () => Promise<void>) => Promise<void>;
type Fixtures = {
  expected4xx: Expected4xx[];
  audit: { check: () => void; watch: (context: BrowserContext) => void };
  step: Step;
  actor: (account: string) => Promise<Page>;
};

export const test = base.extend<Fixtures>({
  expected4xx: [[], { option: true }],
  audit: [async ({ context, expected4xx, baseURL }, use, testInfo) => {
    const errors: string[] = [];
    const ignored: string[] = [];
    const observed: Expected4xx[] = [];
    function watch(target: BrowserContext) {
      target.on('console', message => {
        if (message.type() !== 'error') return;
        const text = message.text();
        const blockedScript = /^Loading the script '([^']+)' violates the following Content Security Policy\b/.exec(text);
        if (blockedScript && baseURL) {
          try {
            if (new URL(blockedScript[1]).origin !== new URL(baseURL).origin) {
              ignored.push(`console.error: ${text}`);
              return;
            }
          } catch {
            // Нераспознанный URL остаётся ошибкой: фильтруем только доказанно чужие скрипты.
          }
        }
        errors.push(`console.error: ${text}`);
      });
      target.on('weberror', event => errors.push(`pageerror: ${event.error().message}`));
      target.on('response', response => {
        const path = new URL(response.url()).pathname;
        if (!path.startsWith('/api/v1/') || response.status() < 400) return;
        const failure = { method: response.request().method(), path, status: response.status() };
        observed.push(failure);
        if (failure.status >= 500 || !expected4xx.some(item => item.method === failure.method && item.path === failure.path && item.status === failure.status)) {
          errors.push(`${failure.method} ${path} → ${failure.status}`);
        }
      });
    }
    const check = () => { expect(errors, 'На каждом шаге: без ошибок браузера, 5xx и неожиданных 4xx').toEqual([]); };
    watch(context);
    await use({ check, watch });
    await testInfo.attach('browser-api-audit', { body: JSON.stringify({ errors, ignored, observed, annotations: testInfo.annotations }, null, 2), contentType: 'application/json' });
    check();
  }, { auto: true }],
  step: async ({ audit }, provide) => {
    await provide(async (name, body) => { await base.step(name, async () => { await body(); audit.check(); }); });
  },
  actor: async ({ browser, baseURL, viewport, audit }, provide, testInfo) => {
    const actors: { account: string; context: BrowserContext; page: Page }[] = [];
    await provide(async account => {
      const context = await browser.newContext({ baseURL, viewport: viewport ?? undefined, serviceWorkers: 'block', reducedMotion: 'reduce' });
      audit.watch(context);
      const page = await context.newPage();
      actors.push({ account, context, page });
      await login(page, account);
      return page;
    });
    for (const { account, context, page } of actors) {
      await testInfo.attach(`${account}-screen`, { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' });
      await context.close();
    }
  },
});
export { expect };

export async function login(page: Page, account: string) {
  await page.goto('/login');
  await page.getByLabel(/^Логин/).fill(account);
  await page.getByLabel(/^Пароль/).fill(process.env.VISUAL_PASSWORD ?? 'demo2026');
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('heading', { name: account === 'underwriter' ? 'Очередь' : 'Мои заявки', exact: true })).toBeVisible();
}

const purposes: Record<string, string> = { WORKING_CAPITAL: 'Оборотные средства', EQUIPMENT: 'Оборудование и развитие' };
const products: Record<string, string> = { EXPRESS: 'Экспресс-кредит', WORKING_CAPITAL: 'Оборотный кредит' };

export async function createApplication(page: Page, customer: Persona, account = customer.code, inspect: () => Promise<void> = async () => {}) {
  await login(page, account);
  await page.goto('/app/applications/new');
  await page.getByRole('button', { name: 'Кассовый разрыв', exact: true }).click();
  await inspect();
  const product = page.locator('article, section').filter({ has: page.getByRole('heading', { name: products[customer.demo.app.product], exact: true }) });
  await product.getByRole('button', { name: 'Выбрать', exact: true }).click();
  await page.getByLabel('Сумма, ₽', { exact: true }).fill(String(customer.demo.app.amount));
  await page.getByRole('combobox', { name: 'Срок, мес.', exact: true }).click();
  await page.getByRole('option', { name: String(customer.demo.app.term), exact: true }).click();
  await page.getByRole('combobox', { name: 'Цель', exact: true }).click();
  await page.getByRole('option', { name: purposes[customer.demo.app.purpose], exact: true }).click();
  await page.getByLabel('Выручка за год, ₽', { exact: true }).fill(String(customer.demo.app.declared_revenue_year));
  await inspect();
  await page.getByRole('button', { name: 'Создать заявку', exact: true }).click();
  await expect(page).toHaveURL(/\/app\/applications\/[0-9a-f-]{36}$/);
  const id = new URL(page.url()).pathname.split('/').pop()!;
  expect(id).toMatch(/^[0-9a-f-]{36}$/);
  test.info().annotations.push({ type: 'application', description: id });
  await expect(page.getByRole('region', { name: 'Согласия и отправка', exact: true })).toBeVisible();
  await inspect();
  return id;
}

export async function confirmOtp(page: Page, confirmLabel: string) {
  // OtpConfirm запрашивает код автоматически при открытии блока.
  await expect(page.getByRole('button', { name: 'Подставить', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Подставить', exact: true }).click();
  await expect(page.getByLabel('Код из СМС', { exact: true })).toHaveValue(/^\d{6}$/);
  await page.getByRole('button', { name: confirmLabel, exact: true }).click();
}

export async function submitApplication(page: Page, customer: Persona) {
  const checks = page.getByRole('region', { name: 'Согласия и отправка', exact: true }).getByRole('checkbox');
  await expect(checks).toHaveCount(customer.kind === 'IP' ? 3 : 2);
  for (const check of await checks.all()) await check.check();
  await page.getByRole('button', { name: 'Подписать и отправить', exact: true }).click();
  await confirmOtp(page, 'Подтвердить и отправить');
}

export const money = (value: number) => `${value.toLocaleString('ru-RU')} ₽`;

export async function assertOffer(page: Page, offer: Offer) {
  await expect(page.getByRole('button', { name: 'Принять предложение', exact: true })).toBeVisible({ timeout: 60_000 });
  const terms = page.getByRole('region', { name: /^(Условия|Мы предлагаем)$/ });
  const amount = await terms.getAttribute('aria-label') === 'Условия' ? page.getByText(/^Банк одобрил/) : terms;
  await expect(amount).toContainText(money(offer.amount));
  await expect(terms).toContainText(`${offer.term_months} мес.`);
  await expect(terms).toContainText(`${offer.rate.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} %`);
  await expect(terms).toContainText(money(offer.monthly_payment));
}

export async function acceptAndSign(page: Page, guarantor: boolean) {
  await page.getByRole('button', { name: 'Принять предложение', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Подписать договор', exact: true })).toBeVisible({ timeout: 60_000 });
  await page.getByRole('button', { name: 'Подписать договор', exact: true }).click();
  await confirmOtp(page, 'Подтвердить подпись');
  if (guarantor) {
    await expect(page.getByRole('button', { name: 'Подписать поручительство', exact: true })).toBeVisible({ timeout: 60_000 });
    await page.getByRole('button', { name: 'Подписать поручительство', exact: true }).click();
    await confirmOtp(page, 'Подтвердить подпись');
  }
}

export async function approve(bank: Page, comment: string) {
  const form = bank.getByRole('region', { name: 'Решение', exact: true });
  await form.getByText('Одобрить', { exact: true }).click();
  await form.getByLabel('Комментарий (обязательно)', { exact: true }).fill(comment);
  await form.getByRole('button', { name: 'Принять решение', exact: true }).click();
  await expect(bank.getByRole('region', { name: 'Решение принято', exact: true })).toBeVisible({ timeout: 60_000 });
}
