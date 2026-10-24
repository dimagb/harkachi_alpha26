import assert from 'node:assert/strict';
import console from 'node:console';
import process from 'node:process';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath, URL } from 'node:url';
import { chromium } from '@playwright/test';

// Run against `VITE_USE_MSW=true npm run dev`. --check validates without screenshots.
const appUrl = process.env.VISUAL_APP_URL ?? 'http://127.0.0.1:5173';
const out = fileURLToPath(new URL('./out/', import.meta.url));
const screenshots = !process.argv.includes('--check');
const scenario = process.argv.find((argument) => argument.startsWith('--scenario='))?.slice('--scenario='.length);
if (screenshots) await mkdir(out, { recursive: true });
const browser = await chromium.launch(process.env.VISUAL_BROWSER ? { channel: process.env.VISUAL_BROWSER } : {});
try {
  for (const [key, login, label, suffix] of [
    ['ip_draft', 'ip_good', 'Согласия и отправка', '000000000301'],
    ['accountant_draft', 'ooo_load_accountant', 'Согласия и отправка', '000000000303'],
    ['ooo_signing', 'ooo_load', 'Подписание', '000000000304'],
    ['ip_disbursed', 'ip_good', 'Выдача', '000000000305'],
  ]) {
    if (scenario && scenario !== key) continue;
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.goto(`${appUrl}/login`);
    await page.getByLabel(/^Логин/).fill(login);
    await page.getByLabel(/^Пароль/).fill('demo2026');
    await page.getByRole('button', { name: 'Войти', exact: true }).click();
    await page.getByRole('heading', { name: 'Мои заявки', exact: true }).waitFor();
    await page.goto(`${appUrl}/app/applications/30000000-0000-4000-8000-${suffix}`);
    await page.getByRole('region', { name: label, exact: true }).waitFor();
    if (key === 'accountant_draft') {
      assert.equal(await page.getByRole('checkbox').count(), 0);
      await page.getByRole('button', { name: 'Отправить на подпись директору', exact: true }).waitFor();
    }
    if (key === 'ooo_signing') assert.equal(await page.getByText('это вы', { exact: true }).count(), 2);
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1100 });
      await page.evaluate(() => globalThis.document.fonts.ready);
      await page.waitForTimeout(300);
      const dimensions = await page.evaluate(() => ({ content: globalThis.document.documentElement.scrollWidth, viewport: globalThis.innerWidth }));
      assert(dimensions.content <= dimensions.viewport, `${key}: горизонтальный скролл на ${width} px`);
      if (screenshots) await page.screenshot({ path: `${out}/signing-${key}-${width}.png`, fullPage: true });
      console.log(`${key}: ${width} px, горизонтального скролла нет`);
    }
    await context.close();
  }
} finally { await browser.close(); }
