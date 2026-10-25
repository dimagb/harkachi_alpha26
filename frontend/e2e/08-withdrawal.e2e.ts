import { test, expect, persona, createApplication, submitApplication } from './helpers';

// Ловит неработающий отзыв и отсутствие подтверждения перед закрытием заявки.
test('08 ooo_border — отзыв заявки в работе', async ({ page, step }) => {
  let id: string;
  await step('Собственная заявка на рассмотрении специалиста', async () => {
    const customer = persona('ooo_border');
    id = await createApplication(page, customer);
    await submitApplication(page, customer);
    await expect(page.getByRole('region', { name: 'Что происходит с заявкой', exact: true })).toContainText('Заявку рассматривает специалист', { timeout: 60_000 });
  });
  await step('Отзыв с подтверждением', async () => {
    await page.getByRole('button', { name: 'Отозвать заявку', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Отозвать', exact: true }).click();
    await expect(dialog).not.toBeVisible();
    await expect(page.getByText('Отозвана', { exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('button', { name: 'Отозвать заявку', exact: true })).toHaveCount(0);
  });
  await step('Отзыв сохранён после повторного открытия своей заявки', async () => {
    await page.goto('/app');
    const own = page.locator(`a[href="/app/applications/${id}"]`);
    await expect(own).toContainText(/отозвана/i);
    await own.click();
    await expect(page.getByText('Отозвана', { exact: true })).toBeVisible();
  });
});
