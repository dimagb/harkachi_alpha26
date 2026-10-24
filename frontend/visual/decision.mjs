import assert from 'node:assert/strict';
import console from 'node:console';
import process from 'node:process';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, URL } from 'node:url';
import { chromium } from '@playwright/test';
import { createServer } from 'vite';
import { setupServer } from 'msw/node';

const appUrl = process.env.VISUAL_APP_URL ?? 'http://127.0.0.1:5173';
const designUrl = process.env.VISUAL_DESIGN_URL ?? 'http://127.0.0.1:8090';
const out = fileURLToPath(new URL('./out/', import.meta.url));
await mkdir(out, { recursive: true });
const fontDir = new URL('../node_modules/@fontsource/onest/files/', import.meta.url);
const fonts = (await readdir(fontDir)).filter((name) => /^onest-(cyrillic|latin)-(400|500|600)-normal\.woff2$/.test(name));
const localFonts = (await Promise.all(fonts.map(async (name) => {
  const weight = name.match(/-(\d+)-normal/)[1];
  const range = name.includes('cyrillic') ? 'U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116' : 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';
  return `@font-face{font-family:Onest;font-style:normal;font-weight:${weight};font-display:block;src:url(data:font/woff2;base64,${(await readFile(new URL(name, fontDir))).toString('base64')}) format('woff2');unicode-range:${range}}`;
}))).join('\n');
const browser = await chromium.launch(process.env.VISUAL_BROWSER ? { channel: process.env.VISUAL_BROWSER } : {});
// Exercise the same MSW handlers as Vitest; the dev server can stay configured for the real API.
const vite = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
const { createHandlers } = await vite.ssrLoadModule('/src/mocks/handlers.ts');
const mocks = setupServer(...createHandlers());
mocks.listen({ onUnhandledFrame: 'bypass' });
const rows = [];
let unexpected = 0;
const surface = ['background-color', 'padding', 'gap', 'border', 'border-radius'];
const typography = ['font-family', 'font-size', 'font-weight', 'line-height', 'letter-spacing', 'color'];
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
  await context.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const response = await globalThis.fetch(request.url(), { method: request.method(), headers: request.headers(), ...(request.postData() ? { body: request.postData() } : {}) });
    await route.fulfill({ status: response.status, headers: Object.fromEntries(response.headers), body: await response.text() });
  });
  const design = await context.newPage();
  await design.route('https://fonts.googleapis.com/**', (route) => route.abort());
  await design.route('https://fonts.gstatic.com/**', (route) => route.abort());
  await design.goto(`${designUrl}/decision.html`);
  await design.locator('[id="1a"] main').waitFor();
  await design.addStyleTag({ content: localFonts });
  await design.evaluate(() => globalThis.document.fonts.ready);
  async function compare(block, left, right, properties, exceptions = {}) {
    const computed = (locator) => locator.evaluate((element, names) => Object.fromEntries(names.map((name) => [name, globalThis.getComputedStyle(element).getPropertyValue(name)])), properties);
    const a = await computed(left), b = await computed(right);
    for (const property of properties) {
      const equal = a[property] === b[property];
      const reason = property === 'font-family' && a[property].startsWith('Onest') && b[property].startsWith('Onest') ? 'Onest, отличаются резервные семейства' : exceptions[property];
      if (!equal && !reason) unexpected++;
      rows.push([block, property, a[property], b[property], equal ? 'совпадает' : reason ? `допущено: ${reason}` : 'НЕ СОВПАДАЕТ']);
    }
  }
  for (const [login, variant, id] of [['ip_good', '1a', '000000000001'], ['ooo_load', '1b', '000000000002'], ['ip_bad', '1c', '000000000201']]) {
    mocks.resetHandlers(...createHandlers());
    const ours = await context.newPage();
    await ours.goto(`${appUrl}/login`);
    await ours.getByLabel(/^Логин/).fill(login);
    await ours.getByLabel(/^Пароль/).fill('demo2026');
    await ours.getByRole('button', { name: 'Войти', exact: true }).click();
    await ours.getByRole('heading', { name: 'Мои заявки', exact: true }).waitFor();
    await ours.goto(`${appUrl}/app/applications/30000000-0000-4000-8000-${id}`);
    await ours.getByRole('region', { name: 'Решение банка', exact: true }).waitFor();
    await ours.getByText(`Данные из ${login === 'ooo_load' ? 'ЕГРЮЛ' : 'ЕГРИП'} на 23.10.2026`, { exact: true }).waitFor();
    assert.equal(await ours.getByText('Не удалось выполнить действие', { exact: true }).count(), 0);
    await ours.evaluate(() => globalThis.document.fonts.ready);
    const reference = design.locator(`[id="${variant}"] main`);
    const blocks = [];
    if (login === 'ip_good') {
      blocks.push(['terms', reference.getByRole('heading', { name: 'Условия', exact: true }).locator('..'), ours.getByRole('region', { name: 'Условия', exact: true })]);
      blocks.push(['why', reference.getByRole('heading', { name: 'Почему одобрили', exact: true }).locator('..'), ours.getByRole('region', { name: 'Почему одобрили', exact: true })]);
    } else if (login === 'ooo_load') {
      const comparison = await ours.getByRole('region', { name: 'Сравнение условий', exact: true }).boundingBox();
      const explanation = await ours.getByRole('region', { name: 'Почему одобрили', exact: true }).boundingBox();
      assert(comparison && explanation && explanation.x >= comparison.x + comparison.width, '1440: «Почему одобрили» справа от сравнения');
      assert.equal(await ours.getByRole('region', { name: 'Условия', exact: true }).count(), 0);
      for (const [name, text] of [['requested', 'Вы просили'], ['proposed', 'Мы предлагаем']]) blocks.push([name, reference.getByText(text, { exact: true }).locator('..'), ours.getByRole('region', { name: text, exact: true })]);
      assert.equal(await ours.getByRole('region', { name: 'Вы просили' }).getByText('Ставка', { exact: true }).count(), 0);
      await ours.getByRole('region', { name: 'Вы просили' }).getByText(/^около/).waitFor();
      console.log('Встречное: ставка запрошенных условий отсутствует, платёж через /calculator; поручитель без «Это вы» — по F-05.');
    } else {
      blocks.push(['reason', reference.getByText('Причина', { exact: true }).locator('../..'), ours.getByRole('region', { name: 'Причина отказа' })]);
      blocks.push(['objection', reference.getByText('Не согласны с решением?', { exact: true }).locator('../..'), ours.getByRole('region', { name: 'Пересмотр решения' })]);
      console.log('Отказ: текст и действие из codes.md, дата из retry_after; категория 600 — по F-05.');
    }
    for (const [name, left, right] of blocks) {
      await left.screenshot({ path: `${out}/decision-${name}-design.png` });
      await right.screenshot({ path: `${out}/decision-${name}-ours.png` });
      await compare(name, left, right, surface);
    }
    await compare(`${login}: заголовок`, reference.locator('header h2'), ours.locator('h2').first(), typography);
    if (login === 'ip_good') {
      await compare('плитка', blocks[0][1].getByText('Ставка', { exact: true }).locator('..'), blocks[0][2].getByText('Ставка', { exact: true }).locator('..'), surface);
      await compare('значение плитки', blocks[0][1].getByText('22%', { exact: true }), blocks[0][2].getByText('22 %', { exact: true }), typography);
      await compare('галочка', blocks[1][1].locator('li>span').first(), blocks[1][2].locator('li>span').first(), ['width', 'height', 'background-color', 'border-radius']);
    }
    await ours.screenshot({ path: `${out}/decision-${login}-1440.png`, fullPage: true });
    await ours.setViewportSize({ width: 375, height: 1100 });
    await ours.evaluate(() => globalThis.document.fonts.ready);
    await ours.waitForTimeout(300);
    await ours.waitForFunction(() => {
      const stages = globalThis.document.querySelectorAll('[aria-label="Этапы заявки"] > li');
      return stages.length === 6 && stages[1].getBoundingClientRect().y > stages[0].getBoundingClientRect().y;
    });
    const overflow = await ours.evaluate(() => ({
      width: globalThis.document.documentElement.scrollWidth,
      viewport: globalThis.innerWidth,
      elements: [...globalThis.document.querySelectorAll('body *')].flatMap((element) => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && (rect.right > globalThis.innerWidth || rect.left < 0) ? [{ tag: element.tagName, class: element.className, text: element.textContent?.slice(0, 100), left: rect.left, right: rect.right, width: rect.width }] : [];
      }),
    }));
    if (overflow.width > overflow.viewport) console.error(`${login}: элементы за границами 375 px`, overflow);
    assert.equal(overflow.width > overflow.viewport, false, `${login}: горизонтальный скролл на 375`);
    const stages = ours.getByRole('list', { name: 'Этапы заявки' }).getByRole('listitem');
    // Read both rectangles in one frame: scrolling can change between two protocol calls.
    assert(await stages.evaluateAll((items) => items[1].getBoundingClientRect().y > items[0].getBoundingClientRect().y));
    await ours.screenshot({ path: `${out}/decision-${login}-375.png`, fullPage: true });
    console.log(`${login}: 1440/375 px, вертикальная лента, горизонтального скролла нет`);
    await ours.close();
  }
  await design.locator('[id="1d"] [data-screen-label]').screenshot({ path: `${out}/decision-mobile-design.png` });
  const table = ['| Блок | Свойство | Макет | Наш | Результат |', '| --- | --- | --- | --- | --- |', ...rows.map((row) => `| ${row.join(' | ')} |`)].join('\n');
  await writeFile(`${out}/decision-computed.md`, table + '\n');
  await writeFile(`${out}/decision-computed.json`, JSON.stringify(rows, null, 2));
  console.log(table);
  console.log(`Необъяснённых отличий computed: ${unexpected}`);
  if (unexpected) process.exitCode = 1;
  await context.close();
} finally { mocks.close(); await vite.close(); await browser.close(); }
