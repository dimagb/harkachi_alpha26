import { test, expect, persona, createApplication, submitApplication } from './helpers';

// Ловит раскрытие скрытых проверок в видимом тексте любого клиентского экрана заявки.
test('06 ooo_aml — дополнительные проверки без внутренних обозначений', async ({ page, step }) => {
  const customer = persona('ooo_aml');
  const inspect = async () => {
    expect(await page.locator('body').innerText(), 'Клиент не видит скрытые основания проверки').not.toMatch(/AML|ПОД\/ФТ|115-ФЗ|стоп-фактор|SF_/i);
  };
  let id: string;
  await step('Безопасный текст подбора, формы и черновика', async () => {
    id = await createApplication(page, customer, customer.code, inspect);
  });
  await step('Согласия, подача и публичная категория отказа', async () => {
    await submitApplication(page, customer);
    await inspect();
    const reason = page.getByRole('region', { name: 'Причина отказа', exact: true });
    await expect(reason).toContainText('Дополнительные проверки', { timeout: 60_000 });
    await inspect();
    await expect(page.getByRole('button', { name: 'Попросить пересмотр', exact: true })).toHaveCount(0);
  });
  await step('Все раскрытия карточки и повторный переход из списка', async () => {
    const expanders = page.locator('main [aria-expanded="false"]');
    while (await expanders.count()) {
      await expanders.first().click();
      await inspect();
    }
    await page.goto('/app');
    const own = page.locator(`a[href="/app/applications/${id}"]`);
    await expect(own).toBeVisible();
    await inspect();
    await own.click();
    await expect(page.getByRole('region', { name: 'Причина отказа', exact: true })).toBeVisible();
    await inspect();
  });
});
