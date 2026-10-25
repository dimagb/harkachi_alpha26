import { test, expect, persona, createApplication, submitApplication, approve, money } from './helpers';
import type { Page } from '@playwright/test';

// Ловит неработающий пересмотр и отсутствие следа решения вопреки стоп-фактору.
test('05 ip_bad — отказ, пересмотр и одобрение', async ({ page, actor, step }) => {
  const customer = persona('ip_bad');
  const objection = 'Просрочка уже погашена. Прошу проверить обновлённые сведения и пересмотреть решение.';
  let id: string;
  let bank: Page;
  await step('Собственная заявка и понятный отказ', async () => {
    id = await createApplication(page, customer);
    await submitApplication(page, customer);
    const reason = page.getByRole('region', { name: 'Причина отказа', exact: true });
    await expect(reason).toBeVisible({ timeout: 60_000 });
    await expect(reason).toContainText(/просроч|кредитн.*истор/i);
    await expect(reason).toContainText('Что можно сделать');
    await expect(page.locator('body')).not.toContainText(/SF_|GRADE_|стоп-фактор/i);
  });
  await step('Клиент отправляет обращение из блока несогласия', async () => {
    const reconsider = page.getByRole('region', { name: 'Пересмотр решения', exact: true });
    await expect(reconsider).toContainText('Не согласны с решением?');
    await reconsider.getByRole('button', { name: 'Попросить пересмотр', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Почему вы не согласны', { exact: true }).fill(objection);
    await dialog.getByRole('button', { name: 'Отправить обращение', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Пересмотр решения', exact: true })).toContainText('Ваше обращение рассматривает специалист банка', { timeout: 60_000 });
  });
  await step('Банк видит текст обращения именно в этой заявке', async () => {
    bank = await actor('underwriter');
    await bank.goto(`/bank/applications/${id}`);
    await bank.getByRole('tab', { name: 'История заявки', exact: true }).click();
    await expect(bank.getByRole('tabpanel')).toContainText(objection);
  });
  await step('Одобрение, отметка о стоп-факторе и оферта клиенту', async () => {
    await approve(bank, 'Проверил обращение F-09, одобряю вопреки стоп-фактору');
    await expect(bank.getByRole('tabpanel')).toContainText(/вопреки стоп-фактору/i);
    await expect(page.getByRole('button', { name: 'Принять предложение', exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/^Банк одобрил/)).toContainText(money(customer.demo.app.amount));
    await expect(page.getByRole('region', { name: 'Условия', exact: true })).toContainText(`${customer.demo.app.term} мес.`);
  });
});
