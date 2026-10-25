import { test, expect, persona, createApplication, submitApplication, assertOffer, confirmOtp, money } from './helpers';
import type { Page } from '@playwright/test';

// Ловит потерю передачи директору, прав подписанта или одной из двух подписей.
test('03 ooo_load — бухгалтер, директор и две подписи', async ({ page, actor, step }) => {
  const customer = persona('ooo_load');
  let id: string;
  let director: Page;
  await step('Бухгалтер создаёт заявку и передаёт директору', async () => {
    id = await createApplication(page, customer, 'ooo_load_accountant');
    await expect(page.getByRole('checkbox')).toHaveCount(0);
    await expect(page.getByText('Отправить заявку может руководитель или сотрудник с правом подписи')).toBeVisible();
    await page.getByRole('button', { name: 'Отправить на подпись директору', exact: true }).click();
    await expect(page.getByText('Отправлено на подпись — руководитель увидит заявку в своём списке', { exact: true })).toBeVisible();
  });
  await step('Директор видит действие именно по созданной заявке и подаёт её', async () => {
    director = await actor('ooo_load');
    const own = director.locator(`a[href="/app/applications/${id}"]`);
    await expect(own).toContainText('Нужно ваше действие');
    await own.click();
    await expect(director).toHaveURL(new RegExp(`/app/applications/${id}$`));
    await submitApplication(director, customer);
  });
  await step('Встречное предложение по golden и понятное сравнение', async () => {
    await assertOffer(director, customer.demo.expected.offer!);
    await expect(director.getByRole('region', { name: 'Вы просили', exact: true })).toContainText(money(customer.demo.app.amount));
    await expect(director.getByRole('region', { name: 'Сравнение условий', exact: true })).toContainText(/поручител/i);
  });
  await step('Договор и поручительство подписывает директор; выдача', async () => {
    await director.getByRole('button', { name: 'Принять предложение', exact: true }).click();
    const parties = director.getByRole('region', { name: 'Подписание', exact: true });
    await expect(parties.getByText('это вы', { exact: true })).toHaveCount(2);
    await expect(director.getByRole('button', { name: 'Подписать договор', exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(parties.getByRole('button', { name: 'Подписать поручительство', exact: true })).toHaveCount(0);
    await director.getByRole('button', { name: 'Подписать договор', exact: true }).click();
    await confirmOtp(director, 'Подтвердить подпись');
    await expect(parties.getByText('✓ Подписано', { exact: true })).toHaveCount(1);
    await director.getByRole('button', { name: 'Подписать поручительство', exact: true }).click();
    await confirmOtp(director, 'Подтвердить подпись');
    await expect(director.getByText(/Кредит выдан/).first()).toBeVisible({ timeout: 60_000 });
    await expect(director.getByRole('region', { name: 'Выдача', exact: true })).toContainText(money(customer.demo.expected.offer!.amount));
  });
});
