import { test, expect, createApplication, submitApplication, assertOffer, acceptAndSign, persona, money } from './helpers';

// Ловит неверные условия, пропавшую подпись и выдачу без полного графика.
test('01 ip_good — от подачи до выдачи', async ({ page, step }) => {
  const customer = persona('ip_good');
  const offer = customer.demo.expected.offer!;
  await step('Подбор и создание собственной заявки', async () => {
    await createApplication(page, customer);
  });
  await step('Три согласия, подача и оферта по golden', async () => {
    await submitApplication(page, customer);
    await assertOffer(page, offer);
    await expect(page.locator('body')).not.toContainText(/балл|класс|GRADE_/i);
  });
  await step('Принятие, подпись кодом и выдача', async () => {
    await acceptAndSign(page, false);
    await expect(page.getByText(/Кредит выдан/).first()).toBeVisible({ timeout: 60_000 });
    const issued = page.getByRole('region', { name: 'Выдача', exact: true });
    await expect(issued).toContainText(money(offer.amount));
    const rows = issued.locator('tbody tr');
    await expect(rows).toHaveCount(offer.term_months);
    await expect(rows.first().locator('td').nth(2)).toHaveText(money(offer.monthly_payment));
    await expect(rows.last().locator('td').last()).toHaveText(money(0));
  });
});
