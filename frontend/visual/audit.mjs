// A-08: автообход интерфейса на настоящем стенде (без MSW), только чтение.
// VISUAL_BROWSER=chrome VISUAL_APP_URL=http://localhost:8080 node visual/audit.mjs
import console from 'node:console';
import process from 'node:process';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, URL } from 'node:url';
import { chromium } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';

const appUrl = (process.env.VISUAL_APP_URL ?? 'http://localhost:8080').replace(/\/$/, '');
const password = process.env.VISUAL_PASSWORD ?? 'demo2026';
const workers = Number(process.env.VISUAL_WORKERS ?? 4);
const out = fileURLToPath(new URL('./out/audit/', import.meta.url));
await mkdir(out, { recursive: true });

// Белый список латиницы в видимом тексте: дополнять, а не прятать находки.
const LATIN_ALLOWED = new Set(['Alfa', 'PDF', 'API', 'ОКВЭД']);
// Ожидаемые ответы 4xx: «метод путь-шаблон код». Пока ни одного.
const EXPECTED_4XX = new Set([]);
const CLIENTS = ['ip_good', 'ooo_load', 'ooo_load_accountant', 'ooo_gap', 'ip_bad', 'ooo_border', 'ooo_aml'];
const VIEWPORTS = { 1440: { width: 1440, height: 1000 }, 1366: { width: 1366, height: 768 }, 375: { width: 375, height: 812 } };
// Кнопки, которые меняют данные, не нажимаем никогда.
const UNSAFE = /отправ|подпис|принять|отказ|отозв|получить код|соглас|удал|перемот|выдат|возраж|одобр|встречн|запрос|сохран|подтвер|продолж|выйти|меню/i;
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

const findings = [];
const pages = [];
const started = Date.now();

function template(path) {
  return path.replace(UUID, '{id}').replace(/\/\d+(?=\/|$)/g, '/{n}');
}

async function run(account, size, bank) {
  const viewport = VIEWPORTS[size];
  const browser = await chromium.launch(process.env.VISUAL_BROWSER ? { channel: process.env.VISUAL_BROWSER } : {});
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, reducedMotion: 'reduce', serviceWorkers: 'block' });
  const page = await context.newPage();
  let where = 'login';
  const add = (kind, detail, extra = {}) => findings.push({ account, width: size, page: where, kind, detail, bank: bank && kind === 'text-code', ...extra });
  page.on('console', message => {
    if (['error', 'warning'].includes(message.type())) add(message.type() === 'error' ? 'console-error' : 'console-warn', message.text().slice(0, 300));
  });
  page.on('pageerror', error => add('pageerror', error.message.slice(0, 300)));
  const data = {};
  page.on('response', async response => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith('/api/v1/')) return;
    const method = response.request().method();
    const path = url.pathname.slice('/api/v1'.length);
    if (response.status() >= 400) {
      const key = `${method} ${template(path)} ${response.status()}`;
      add(response.status() >= 500 ? 'api-5xx' : EXPECTED_4XX.has(key) ? 'api-4xx-expected' : 'api-4xx', `${method} ${path}${url.search} → ${response.status()}`);
      return;
    }
    if (method === 'GET' && ['/applications', '/underwriting/queue', '/bank/applications'].includes(path)) {
      try { data[path] = await response.json(); } catch { /* тело уже не нужно */ }
    }
  });

  async function settle() {
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.locator('[role="status"]').first().waitFor({ state: 'detached', timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(150);
  }

  async function inspect(label, { axe = true } = {}) {
    where = label;
    await settle();
    const result = await page.evaluate(() => {
      const doc = globalThis.document;
      const text = doc.body.innerText;
      const visible = element => {
        const box = element.getBoundingClientRect();
        const style = globalThis.getComputedStyle(element);
        return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      };
      const empty = [...doc.querySelectorAll('h1, h2, h3, h4, h5, h6, [class*="badge" i], .mantine-Badge-root')]
        .filter(element => visible(element) && !element.innerText.trim() && !element.querySelector('svg, img'))
        .map(element => `${element.tagName.toLowerCase()}.${String(element.className).split(' ')[0]}`);
      return { text, empty, scroll: doc.documentElement.scrollWidth, viewport: globalThis.innerWidth };
    });
    pages.push({ account, width: size, page: label });
    let found = 0;
    const note = (kind, detail) => { add(kind, detail); found += 1; };
    if (result.scroll > result.viewport) note('h-scroll', `${result.scroll} > ${result.viewport} px`);
    for (const code of new Set(result.text.match(/\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b/g) ?? [])) note('text-code', code);
    const latin = new Set((result.text.match(/\b[A-Za-z]{3,}\b/g) ?? []).filter(word => !LATIN_ALLOWED.has(word) && !/^[A-Z][A-Z0-9]*_/.test(word)));
    for (const word of latin) if (!/_/.test(word)) note('text-latin', word);
    if (result.text.includes('`')) note('text-backtick', '`');
    for (const bad of ['undefined', 'NaN', 'null', '[object Object]']) {
      const pattern = bad === '[object Object]' ? /\[object Object\]/ : new RegExp(`\\b${bad}\\b`);
      if (pattern.test(result.text)) note('text-bad', bad);
    }
    for (const element of result.empty) note('empty', element);
    if (axe) {
      const report = await new AxeBuilder({ page }).analyze().catch(error => ({ violations: [], error }));
      if (report.error) note('axe-error', String(report.error.message).slice(0, 200));
      for (const violation of report.violations.filter(item => ['critical', 'serious'].includes(item.impact))) {
        note('axe', `${violation.impact} ${violation.id}: ${violation.nodes.length} эл. (${violation.nodes[0]?.target.join(' ')})`);
      }
    }
    if (found) {
      const name = `${account}-${size}-${label.replace(/[^\w\u0400-\u04FF-]+/g, '_').slice(0, 80)}.png`;
      await page.screenshot({ path: `${out}${name}`, fullPage: true }).catch(() => {});
      for (const item of findings.filter(f => f.account === account && f.width === size && f.page === label && !f.shot)) item.shot = name;
    }
  }

  async function open(path, label, options) {
    where = label;
    await page.goto(`${appUrl}${path}`);
    await inspect(label, options);
  }

  // Сбой одного шага — находка «script», обход продолжается.
  async function step(action) {
    try {
      await action();
    } catch (error) {
      add('script', error.message.split('\n')[0]);
    }
  }

  async function clickSafe(locator, label) {
    const count = await locator.count();
    for (let i = 0; i < count; i += 1) {
      const element = locator.nth(i);
      const name = `${await element.innerText().catch(() => '')} ${await element.getAttribute('aria-label') ?? ''}`;
      if (UNSAFE.test(name) || !(await element.isVisible().catch(() => false))) continue;
      await element.click({ timeout: 2000 }).catch(() => {});
    }
    if (count) await inspect(label, { axe: false });
  }

  try {
    await page.goto(`${appUrl}/login`);
    await inspect('/login');
    await page.getByLabel(/^Логин/).fill(account);
    await page.getByLabel(/^Пароль/).fill(password);
    await page.getByRole('button', { name: 'Войти', exact: true }).click();
    await page.getByRole('heading', { name: bank ? 'Очередь' : 'Мои заявки', exact: true }).waitFor();

    if (!bank) {
      await inspect('/app');
      await open('/app/applications/new', '/app/applications/new');
      const purpose = page.getByRole('button', { name: 'Кассовый разрыв', exact: true });
      if (await purpose.count()) {
        await purpose.click();
        await inspect('/app/applications/new · подбор');
        const choose = page.getByRole('button', { name: 'Выбрать', exact: true }).first();
        if (await choose.count()) {
          await choose.click();
          await inspect('/app/applications/new · форма');
        }
      }
      const list = Array.isArray(data['/applications']) ? data['/applications'] : data['/applications']?.items ?? [];
      const seen = new Set();
      for (const item of list) {
        // Каждая заявка — при 1440; на 375 и для axe — по одной на состояние.
        const first = !seen.has(item.state);
        seen.add(item.state);
        if (size === 375 && !first) continue;
        await step(async () => {
          await open(`/app/applications/${item.id}`, `/app/applications/{id} [${item.state}] № ${item.number}`, { axe: first });
          if (first) await clickSafe(page.locator('main [aria-expanded="false"], main [role="tab"][aria-selected="false"]'), `/app/applications/{id} [${item.state}] · раскрытия`);
        });
      }
    } else {
      await inspect('/bank/queue');
      const queue = data['/underwriting/queue'] ?? [];
      for (const item of queue) {
        await step(async () => {
          await open(`/bank/applications/${item.id}`, `/bank/applications/{id} очередь № ${item.number}`);
          await clickSafe(page.getByRole('tab', { selected: false }), `/bank/applications/{id} очередь № ${item.number} · вкладки`);
        });
      }
      await open('/bank/journal', '/bank/journal');
      const journal = data['/bank/applications']?.items ?? [];
      const queued = new Set(queue.map(item => item.id));
      const states = new Map();
      for (const item of journal) if (!queued.has(item.id) && !states.has(item.state)) states.set(item.state, item);
      const sample = [...states.values()].slice(0, 5);
      await step(async () => {
        const events = page.getByRole('button', { name: /^События заявки №/ }).first();
        if (!(await events.count())) return;
        await events.click();
        await inspect('/bank/journal · события', { axe: true });
      });
      await step(async () => {
        const next = page.getByRole('button', { name: 'Следующая страница' });
        if (!(await next.isEnabled().catch(() => false))) return;
        await next.click();
        await inspect('/bank/journal · страница 2', { axe: false });
      });
      // Поле Mantine Select: у списка вариантов та же подпись, поэтому берём именно input.
      const filter = page.getByLabel('Этап', { exact: true }).and(page.locator('input'));
      for (const option of ['Рассмотрение специалистом', 'Отказ', 'Выдана']) {
        await step(async () => {
          await filter.click();
          const choice = page.getByRole('option', { name: option, exact: true });
          if (!(await choice.count())) { await page.keyboard.press('Escape'); return; }
          await choice.click();
          await inspect(`/bank/journal · фильтр «${option}»`, { axe: false });
        });
      }
      for (const item of sample) {
        await step(() => open(`/bank/applications/${item.id}`, `/bank/applications/{id} журнал [${item.state}] № ${item.number}`));
      }
      const protocol = sample[0] ?? queue[0];
      if (protocol) await step(() => open(`/bank/applications/${protocol.id}/protocol`, '/bank/applications/{id}/protocol'));
    }
  } catch (error) {
    add('script', `${error.message.split('\n')[0]}`);
  } finally {
    await browser.close();
  }
}

const jobs = [
  ...CLIENTS.flatMap(account => [1440, 375].map(size => [account, size, false])),
  ...[1440, 1366, 375].map(size => ['underwriter', size, true]),
];
const queue = [...jobs];
await Promise.all(Array.from({ length: workers }, async () => {
  while (queue.length) {
    const [account, size, bank] = queue.shift();
    const start = Date.now();
    await run(account, size, bank);
    console.log(`${account} ${size}: ${((Date.now() - start) / 1000).toFixed(0)} с`);
  }
}));

const seconds = Math.round((Date.now() - started) / 1000);
const fatal = findings.filter(item => ['console-error', 'pageerror', 'api-5xx', 'api-4xx', 'script'].includes(item.kind));
const summary = { appUrl, seconds, accounts: new Set(jobs.map(job => job[0])).size, pages: pages.length, findings: findings.length, fatal: fatal.length };
await writeFile(`${out}audit.json`, JSON.stringify({ summary, pages, findings }, null, 1), 'utf8');

// Сводка: одна строка на (вид, деталь), с числом страниц и примером.
const groups = new Map();
for (const item of findings) {
  const key = `${item.kind}|${item.kind.startsWith('api') ? item.detail.replace(UUID, '{id}') : item.detail}`;
  const group = groups.get(key) ?? { ...item, count: 0, accounts: new Set() };
  group.count += 1;
  group.accounts.add(`${item.account}@${item.width}`);
  groups.set(key, group);
}
const rows = [...groups.values()].sort((a, b) => a.kind.localeCompare(b.kind) || b.count - a.count);
const md = ['| Вид | Находка | Пример страницы | Где (учётка@ширина) | Раз | Снимок |', '| --- | --- | --- | --- | --- | --- |',
  ...rows.map(row => `| ${row.kind}${row.bank ? ' · экран банка' : ''} | ${row.detail.replace(/\|/g, '\\|').replace(/`/g, 'ʼ')} | ${row.page.replace(/\|/g, '\\|')} | ${[...row.accounts].slice(0, 4).join(', ')}${row.accounts.size > 4 ? ` +${row.accounts.size - 4}` : ''} | ${row.count} | ${row.shot ?? '—'} |`)];
await writeFile(`${out}audit.md`, md.join('\n') + '\n', 'utf8');
console.log(`A-08: ${summary.accounts} учёток, ${summary.pages} страниц, ${summary.findings} находок (${rows.length} разных), критичных ${summary.fatal}, ${seconds} с`);
console.log(`Отчёт: ${out}audit.md`);
for (const item of fatal.slice(0, 20)) console.log(`  ✗ ${item.kind} · ${item.account}@${item.width} · ${item.page} · ${item.detail}`);
process.exitCode = fatal.length ? 1 : 0;
