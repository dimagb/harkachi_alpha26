import assert from 'node:assert/strict';
import console from 'node:console';
import process from 'node:process';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, URL } from 'node:url';
import { chromium } from '@playwright/test';

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
const rows = [];
let unexpected = 0;
const typography = ['font-family', 'font-size', 'font-weight', 'line-height', 'letter-spacing', 'color'];
const surface = ['background-color', 'padding', 'gap', 'border', 'border-radius'];
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
  const design = await context.newPage();
  await design.route('https://fonts.googleapis.com/**', (route) => route.abort());
  await design.route('https://fonts.gstatic.com/**', (route) => route.abort());
  await design.goto(`${designUrl}/application-card.html`);
  const reference = design.locator('[id="1b"] main');
  await reference.waitFor();
  await design.addStyleTag({ content: localFonts });
  await design.evaluate(() => globalThis.document.fonts.ready);
  const ours = await context.newPage();
  await ours.goto(`${appUrl}/login`);
  await ours.getByLabel(/^Логин/).fill('ip_good');
  await ours.getByLabel(/^Пароль/).fill('demo2026');
  await ours.getByRole('button', { name: 'Войти', exact: true }).click();
  await ours.getByRole('heading', { name: 'Мои заявки', exact: true }).waitFor();
  const fixtureUrl = `${appUrl}/app/applications/30000000-0000-4000-8000-000000001042`;
  async function openFixture() {
    await ours.goto(fixtureUrl);
    await ours.getByText('около 24 %').waitFor();
    await ours.getByText('Данные из ЕГРИП на 23.10.2026').waitFor();
    await ours.evaluate(() => globalThis.document.fonts.ready);
  }
  await openFixture();
  const nav = ours.getByRole('navigation', { name: 'Главная навигация' });
  assert.equal(await nav.getByRole('link', { name: 'Мои заявки', exact: true }).getAttribute('href'), '/app');
  await nav.getByRole('link', { name: 'Получить финансирование' }).click();
  await ours.getByRole('heading', { name: 'Зачем нужны деньги?' }).waitFor();
  await nav.getByRole('link', { name: 'Мои заявки', exact: true }).click();
  await ours.getByRole('heading', { name: 'Мои заявки', exact: true }).waitFor();
  await openFixture();
  console.log('Навигация: /app и /app/applications/new — OK');

  const designTimeline = reference.getByText('Заявка', { exact: true }).locator('xpath=ancestor::div[contains(@style,"repeat(6")][1]');
  const ourTimeline = ours.getByRole('list', { name: 'Этапы заявки' });
  const designPanel = reference.getByText('Что происходит', { exact: true }).locator('..').locator('..');
  const ourPanel = ours.getByRole('region', { name: 'Что происходит с заявкой' });
  const designTile = reference.getByText('Сумма', { exact: true }).locator('..');
  const ourTile = ours.getByRole('region', { name: 'Ключевые цифры' }).getByText('Сумма', { exact: true }).locator('..');
  const designNode = designTimeline.getByText('!', { exact: true }).locator('xpath=ancestor-or-self::*[@style][1]');
  const ourNode = ourTimeline.locator('[data-status="action_required"] [aria-hidden=true]').first();
  const designNav = design.locator('[id="1b"] nav');
  const blocks = [
    ['badge', reference.getByText('Нужно ваше действие', { exact: true }).first().locator('xpath=ancestor-or-self::*[@style][1]'), ours.locator('[data-variant=light]')],
    ['nodes', designTimeline, ourTimeline],
    ['panel', designPanel, ourPanel],
    ['tile', designTile, ourTile],
    ['detail', reference.getByText('Цель', { exact: true }).locator('..'), ours.getByRole('region', { name: 'Детали заявки' }).locator('dl')],
    ['navbar', designNav, nav],
  ];
  for (const [name, left, right] of blocks) {
    await left.screenshot({ path: `${out}/${name}-design.png` });
    await right.screenshot({ path: `${out}/${name}-ours.png` });
  }
  async function compare(block, left, right, properties, exceptions = {}) {
    async function computed(locator) {
      return locator.evaluate((element, names) => Object.fromEntries(names.map((name) => [name, globalThis.getComputedStyle(element).getPropertyValue(name)])), properties);
    }
    const a = await computed(left), b = await computed(right);
    for (const property of properties) {
      const equal = a[property] === b[property];
      const reason = property === 'font-family' && a[property].startsWith('Onest') && b[property].startsWith('Onest')
        ? 'Тема: одинаковый Onest, разные резервные семейства' : exceptions[property];
      const verdict = equal ? 'совпадает' : reason ? `допущено: ${reason}` : 'НЕ СОВПАДАЕТ';
      if (!equal && !reason) unexpected++;
      rows.push([block, property, a[property], b[property], verdict]);
    }
  }
  await compare('бейдж', blocks[0][1], blocks[0][2], [...typography, ...surface, 'height']);
  await compare('узел действия', designNode, ourNode, [...typography, 'background-color', 'width', 'height', 'border-radius', 'box-shadow', 'align-items', 'justify-content']);
  await compare('будущий узел', designTimeline.getByText('3', { exact: true }).locator('xpath=ancestor-or-self::*[@style][1]'), ourTimeline.locator('[data-status=pending] [aria-hidden=true]').first(), ['font-size', 'font-weight', 'line-height', 'color', 'background-color', 'width', 'height', 'border', 'border-radius']);
  await compare('линия', designNode.locator('..').locator(':scope>span').nth(1), ourTimeline.locator('[data-status=action_required] [aria-hidden=true]').nth(1), ['height', 'background-color', 'margin', 'border-radius']);
  await compare('панель', designPanel, ourPanel, surface.concat('box-shadow'), { 'box-shadow': 'F-04b/2: полоса wait.4 вместо wait.6' });
  await compare('подпись панели', reference.getByText('Что от вас нужно', { exact: true }), ours.getByText('Что от вас нужно', { exact: true }), typography);
  await compare('текст панели', reference.getByText('Подтвердите выручку до 30.10.2026', { exact: true }).locator('xpath=ancestor-or-self::*[@style][1]'), ourPanel.locator('div').nth(1).locator('span').nth(1), typography);
  await compare('кнопка', reference.getByRole('button', { name: 'Ответить на вопросы банка' }), ourPanel.getByRole('link', { name: 'Ответить на вопросы банка' }), [...typography, 'background-color', 'padding', 'border-radius', 'height']);
  await compare('плитка', designTile, ourTile, surface);
  await compare('подпись плитки', designTile.getByText('Сумма', { exact: true }), ourTile.getByText('Сумма', { exact: true }), typography);
  await compare('значение плитки', designTile.locator('span').nth(1), ourTile.locator('span').nth(1), typography);
  await compare('строка деталей', reference.getByText('Цель', { exact: true }), ours.getByRole('region', { name: 'Детали заявки' }).getByText('Цель', { exact: true }), typography.concat('padding', 'border-top'));
  await compare('шапка: название', reference.getByText('Экспресс-кредит ·', { exact: true }), ours.getByText('Экспресс-кредит ·', { exact: true }), typography);
  await compare('шапка: сумма', reference.locator('header h2 span').nth(1), ours.locator('main h2 span').nth(1), typography);
  await compare('колонка', designNav, nav, ['padding', 'gap', 'border-right']);
  const designNavWidth = (await designNav.boundingBox()).width, ourNavWidth = (await nav.boundingBox()).width;
  rows.push(['колонка', 'rendered width (border-box)', `${designNavWidth}px`, `${ourNavWidth}px`, designNavWidth === ourNavWidth ? 'совпадает' : 'НЕ СОВПАДАЕТ']);
  if (designNavWidth !== ourNavWidth) unexpected++;
  await compare('пункт меню', designNav.getByRole('link', { name: 'Мои заявки', exact: true }), nav.getByRole('link', { name: 'Мои заявки', exact: true }), typography.concat('background-color', 'padding', 'border-radius'));
  const table = ['| Блок | Свойство | Макет | Наш | Результат |', '| --- | --- | --- | --- | --- |', ...rows.map((row) => `| ${row.join(' | ')} |`)].join('\n');
  console.log(table);
  await writeFile(`${out}/computed.md`, table + '\n');
  await writeFile(`${out}/computed.json`, JSON.stringify(rows, null, 2));
  assert.equal(await ours.evaluate(() => globalThis.document.fonts.check('600 16px Onest')), true);
  console.log('fonts.check = true');
  const cdp = await context.newCDPSession(ours);
  await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  const { root } = await cdp.send('DOM.getDocument');
  const renderedFonts = {};
  for (const [label, selector] of [['текст', 'main h2 span:first-child'], ['цифры', 'main h2 span:nth-child(2)']]) {
    const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector });
    renderedFonts[label] = (await cdp.send('CSS.getPlatformFontsForNode', { nodeId })).fonts;
    assert(renderedFonts[label].length && renderedFonts[label].every((font) => /^Onest(?: |$)/.test(font.familyName) && font.isCustomFont));
  }
  console.log('Rendered Fonts: Onest — текст и цифры');
  await writeFile(`${out}/fonts.json`, JSON.stringify(renderedFonts, null, 2));
  await ours.screenshot({ path: `${out}/desktop-ours.png`, fullPage: true });
  await ours.setViewportSize({ width: 375, height: 1100 });
  assert.equal(await ours.evaluate(() => globalThis.document.documentElement.scrollWidth > globalThis.innerWidth), false, '375: горизонтальный скролл');
  const stages = await ourTimeline.getByRole('listitem').all();
  const top = (await stages[0].boundingBox()).y;
  assert((await stages[1].boundingBox()).y > top, '375: лента должна быть вертикальной');
  const caret = ourPanel.locator(':scope>span');
  assert.equal(await caret.evaluate((e) => globalThis.getComputedStyle(e).display), 'none');
  await ours.screenshot({ path: `${out}/mobile-ours.png`, fullPage: true });
  await ourTimeline.screenshot({ path: `${out}/nodes-mobile-ours.png` });
  await design.goto(`${designUrl}/decision.html`);
  await design.locator('[id="1d"] [data-screen-label]').waitFor();
  await design.addStyleTag({ content: localFonts });
  await design.evaluate(() => globalThis.document.fonts.ready);
  await design.locator('[id="1d"] [data-screen-label]').screenshot({ path: `${out}/nodes-mobile-design.png` });
  console.log('375 px: вертикальная лента, указатель скрыт, горизонтального скролла нет');
  console.log(`Необъяснённых отличий computed: ${unexpected}`);
  if (unexpected) process.exitCode = 1;
  await context.close();
} finally { await browser.close(); }
