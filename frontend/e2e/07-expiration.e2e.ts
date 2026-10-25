import { test, expect, persona, createApplication, submitApplication, assertOffer } from './helpers';
import type { Page } from '@playwright/test';

// Ловит незакрытые просроченные оферты/дозапросы и перемотку чужой заявки.
test('07 истечение сроков — оферта 31 день и дозапрос 6 дней', async ({ page, actor, step }) => {
  let bank: Page;
  let offerId: string;
  let infoId: string;
  await step('Собственная оферта ip_good', async () => {
    const customer = persona('ip_good');
    offerId = await createApplication(page, customer);
    await submitApplication(page, customer);
    await assertOffer(page, customer.demo.expected.offer!);
    bank = await actor('underwriter');
  });
  await step('Банк перематывает только эту оферту на 31 день', async () => {
    await timeShift(bank, offerId, 31);
    await assertExpired(page);
  });
  await step('Новая собственная заявка ooo_gap с дозапросом', async () => {
    await page.getByRole('button', { name: 'Выйти', exact: true }).click();
    const customer = persona('ooo_gap');
    infoId = await createApplication(page, customer);
    await submitApplication(page, customer);
    await expect(page.getByRole('region', { name: 'Вопросы банка', exact: true })).toBeVisible({ timeout: 60_000 });
  });
  await step('Банк перематывает только этот дозапрос на 6 дней', async () => {
    await timeShift(bank, infoId, 6);
    await assertExpired(page);
  });
});

async function timeShift(bank: Page, id: string, days: number) {
  await bank.goto(`/bank/applications/${id}`);
  await expect(bank.getByRole('region', { name: 'Параметры заявки', exact: true })).toBeVisible();
  await bank.getByRole('link', { name: 'Журнал банка', exact: true }).click();
  const first = bank.getByRole('button', { name: /^События заявки №/ }).first();
  await expect(first).toBeVisible();
  // Привязка к id из доступного aria-controls, независимо от фоновых заявок и номера страницы.
  const own = bank.locator(`button[aria-controls="events-${id}"]`);
  while (await own.count() === 0) {
    const previous = await first.getAttribute('aria-controls');
    const next = bank.getByRole('button', { name: 'Следующая страница', exact: true });
    await expect(next, `В журнале должна присутствовать своя заявка ${id}`).toBeEnabled();
    await next.click();
    await expect(first).not.toHaveAttribute('aria-controls', previous!);
  }
  await own.click();
  await expect(bank.getByRole('link', { name: 'Открыть карточку', exact: true }).and(bank.locator(`a[href="/bank/applications/${id}"]`))).toBeVisible();
  const row = bank.getByRole('row').filter({ has: own });
  await row.getByRole('button', { name: 'Перемотать время · демо', exact: true }).click();
  const dialog = bank.getByRole('dialog');
  await dialog.getByLabel('Дней', { exact: true }).fill(String(days));
  const shifted = bank.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/demo/time-shift' && response.request().method() === 'POST');
  await dialog.getByRole('button', { name: 'Перемотать', exact: true }).click();
  const response = await shifted;
  expect(response.request().postDataJSON()).toEqual({ application_id: id, days });
  expect(response.ok()).toBe(true);
  expect(await response.json()).toMatchObject({ expired_now: true });
  await expect(dialog).not.toBeVisible();
  await expect(bank.getByText('Срок истёк — заявка закрыта', { exact: true })).toBeVisible();
}

async function assertExpired(page: Page) {
  await page.bringToFront();
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  try {
    await expect(page.getByText('Срок истёк', { exact: true })).toBeVisible({ timeout: 10_000 });
  } catch (error) {
    if (page.isClosed()) throw error;
    test.info().annotations.push({ type: 'finding', description: `После возврата в окно потребовался reload: ${page.url()}` });
    await test.info().attach('before-expiration-reload', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' });
    await page.reload();
  }
  await expect(page.getByText('Срок истёк', { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('link', { name: 'Подать новую заявку', exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('button', { name: 'Принять предложение', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Отправить ответ', exact: true })).toHaveCount(0);
}
