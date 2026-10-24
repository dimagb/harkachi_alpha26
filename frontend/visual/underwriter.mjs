import assert from 'node:assert/strict';
import console from 'node:console';
import process from 'node:process';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, URL } from 'node:url';
import { chromium } from '@playwright/test';

const appUrl = process.env.VISUAL_APP_URL ?? 'http://127.0.0.1:5173';
const designUrl = process.env.VISUAL_DESIGN_URL ?? 'http://127.0.0.1:8090';
const out = fileURLToPath(new URL('./out/underwriter/', import.meta.url));
await mkdir(out, { recursive: true });
const fontDir = new URL('../node_modules/@fontsource/onest/files/', import.meta.url);
const fonts = (await readdir(fontDir)).filter(name => /^onest-(cyrillic|latin)-(400|500|600)-normal\.woff2$/.test(name));
const localFonts = (await Promise.all(fonts.map(async name => {
  const weight = name.match(/-(\d+)-normal/)[1];
  const range = name.includes('cyrillic') ? 'U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116' : 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';
  return `@font-face{font-family:Onest;font-style:normal;font-weight:${weight};font-display:block;src:url(data:font/woff2;base64,${(await readFile(new URL(name, fontDir))).toString('base64')}) format('woff2');unicode-range:${range}}`;
}))).join('\n');
const browser = await chromium.launch(process.env.VISUAL_BROWSER ? { channel: process.env.VISUAL_BROWSER } : {});
const rows = [];
let unexpected = 0;
const typography = ['font-family', 'font-size', 'font-weight', 'line-height', 'letter-spacing', 'color'];
const surface = ['background-color', 'padding', 'gap', 'border', 'border-radius'];
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
  const design = await context.newPage();
  await design.route('https://fonts.googleapis.com/**', route => route.abort());
  await design.route('https://fonts.gstatic.com/**', route => route.abort());
  await design.goto(`${designUrl}/underwriter.html`);
  const reference = design.locator('[data-screen-label="Карточка заявки — андеррайтер"]');
  await reference.getByText('Срок бизнеса', { exact: true }).waitFor();
  await design.addStyleTag({ content: localFonts });
  await design.evaluate(() => globalThis.document.fonts.ready);
  const ours = await context.newPage();
  const pageErrors = [];
  ours.on('pageerror', error => pageErrors.push(error.message));
  // Одинаковое ожидание «12 мин» на повторных запусках, API остаётся MSW.
  await ours.clock.setFixedTime(new Date('2026-10-23T11:15:00Z'));
  await ours.goto(`${appUrl}/login`);
  await ours.getByLabel(/^Логин/).fill('underwriter');
  await ours.getByLabel(/^Пароль/).fill('demo2026');
  await ours.getByRole('button', { name: 'Войти', exact: true }).click();
  await ours.getByRole('heading', { name: 'Очередь', exact: true }).waitFor();
  const nav = ours.getByRole('navigation', { name: 'Навигация банка', exact: true });
  await nav.getByRole('link', { name: 'Очередь · 6' }).waitFor();
  for (const width of [1440, 375]) {
    await ours.setViewportSize({ width, height: 1100 });
    assert.equal(await ours.evaluate(() => globalThis.document.documentElement.scrollWidth > globalThis.innerWidth), false, `${width}: очередь выходит за экран`);
    await ours.screenshot({ path: `${out}/queue-${width}.png`, fullPage: true });
  }
  await ours.setViewportSize({ width: 1440, height: 1100 });
  await ours.getByRole('link', { name: 'Открыть заявку № 1047' }).click();
  await ours.getByRole('heading', { name: 'Факторы оценки', exact: true }).waitFor();
  await ours.getByText('53 875 ₽', { exact: true }).waitFor();
  await ours.evaluate(() => globalThis.document.fonts.ready);
  const designFactor = reference.getByText('Срок бизнеса', { exact: true }).locator('xpath=ancestor::div[contains(@style,"grid-template-columns")][1]');
  const ourFactor = ours.getByRole('button', { name: /Срок бизнеса/ });
  const designRecommendation = reference.getByText('Рекомендация системы', { exact: true }).locator('..').locator('..');
  const ourRecommendation = ours.getByRole('region', { name: 'Рекомендация системы', exact: true });
  const designForm = reference.getByRole('heading', { name: 'Решение', exact: true }).locator('..');
  const ourForm = ours.getByRole('region', { name: 'Решение', exact: true });
  const blocks = [['header', reference.locator('header'), ours.locator('main header')], ['factor', designFactor, ourFactor], ['recommendation', designRecommendation, ourRecommendation], ['form', designForm, ourForm]];
  for (const [name, a, b] of blocks) {
    await a.screenshot({ path: `${out}/${name}-design.png` });
    await b.screenshot({ path: `${out}/${name}-ours.png` });
  }
  async function compare(block, a, b, properties, exceptions = {}) {
    const computed = locator => locator.evaluate((element, names) => Object.fromEntries(names.map(name => [name, globalThis.getComputedStyle(element).getPropertyValue(name)])), properties);
    const left = await computed(a), right = await computed(b);
    for (const property of properties) {
      const same = left[property] === right[property];
      const reason = property === 'font-family' && left[property].includes('Onest') && right[property].includes('Onest') ? 'Onest, резервные семейства темы' : exceptions[property];
      if (!same && !reason) unexpected++;
      rows.push([block, property, left[property], right[property], same ? 'совпадает' : reason ? `допущено: ${reason}` : 'НЕ СОВПАДАЕТ']);
    }
  }
  await compare('шапка', blocks[0][1], blocks[0][2], ['display', 'align-items', 'justify-content', 'gap']);
  await compare('сумма', reference.locator('header h1 span').nth(1), ours.locator('main h1 span').nth(1), typography);
  await compare('компания', reference.locator('header h1 span').first(), ours.locator('main h1 span').first(), typography);
  await compare('строка фактора', designFactor, ourFactor, ['padding', 'border-top', 'display', 'column-gap', 'grid-template-columns'], { 'grid-template-columns': 'ширина первой колонки зависит от переноса шапки; фиксированные колонки 200/140/64 px' });
  await compare('название фактора', reference.getByText('Срок бизнеса', { exact: true }), ourFactor.locator('span').first(), typography);
  await compare('рекомендация', designRecommendation, ourRecommendation, surface);
  await compare('текст рекомендации', designRecommendation.locator(':scope>div').nth(1), ourRecommendation.locator(':scope>div').first(), typography);
  await compare('форма', designForm, ourForm, surface);
  await compare('заголовок формы', designForm.locator('h2'), ourForm.locator('h2'), typography);
  await compare('комментарий', designForm.locator('textarea'), ourForm.locator('textarea'), typography.concat('padding', 'border-radius'), { 'border-color': 'контрастная рамка поля из токенов' });
  const report = ['| Блок | Свойство | Макет | Наш | Результат |', '| --- | --- | --- | --- | --- |', ...rows.map(row => `| ${row.join(' | ')} |`)].join('\n');
  console.log(report);
  await writeFile(`${out}/computed.md`, report + '\n');
  await writeFile(`${out}/computed.json`, JSON.stringify(rows, null, 2));
  assert.equal(await ours.evaluate(() => globalThis.document.fonts.check('600 16px Onest')), true);
  for (const width of [1440, 375]) {
    await ours.setViewportSize({ width, height: 1100 });
    assert.equal(await ours.evaluate(() => globalThis.document.documentElement.scrollWidth > globalThis.innerWidth), false, `${width}: карточка выходит за экран`);
    await ours.screenshot({ path: `${out}/card-${width}.png`, fullPage: true });
  }
  const mobileNav = ours.getByRole('navigation', { name: 'Мобильная навигация банка', exact: true });
  await ours.getByRole('button', { name: 'Меню банка' }).click();
  await mobileNav.getByRole('link', { name: 'Журнал банка' }).waitFor();
  await ours.getByRole('button', { name: 'Меню банка' }).click();
  const factor = ours.getByRole('button', { name: /Платежи к поступлениям/ });
  await factor.click();
  await ours.getByRole('region', { name: 'Первоисточник: Платежи к поступлениям' }).getByText(/150\s000/).waitFor();
  await factor.click();
  assert.deepEqual(pageErrors, [], 'ошибки браузера');
  console.log('MSW: вход underwriter; очередь 6; карточка ooo_border; платёж; раскрытие БКИ; мобильное меню — OK');
  console.log('1440 и 375 px: скриншоты очереди и карточки, горизонтального скролла страницы нет');
  console.log(`Необъяснённых отличий computed: ${unexpected}`);
  if (unexpected) process.exitCode = 1;
  await context.close();
} finally { await browser.close(); }
