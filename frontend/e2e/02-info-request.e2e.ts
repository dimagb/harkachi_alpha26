import { test, expect, persona, createApplication, submitApplication, assertOffer } from './helpers';

// Ловит потерю дозапроса или неверный пересчёт после ответа клиента.
test('02 ooo_gap — дозапрос и одобрение', async ({ page, step }) => {
  const customer = persona('ooo_gap');
  await step('Создание и подача собственной заявки', async () => {
    await createApplication(page, customer);
    await submitApplication(page, customer);
  });
  await step('Запрос подтверждения выручки и ответ по golden', async () => {
    await expect(page.getByRole('region', { name: 'Что происходит с заявкой', exact: true })).toContainText('Нужно уточнить данные', { timeout: 60_000 });
    const questions = page.getByRole('region', { name: 'Вопросы банка', exact: true });
    await expect(questions).toContainText(/выручк/i);
    const answer = customer.demo.info_response![0]!;
    await questions.getByLabel('Выручка за год, ₽', { exact: true }).fill(String(answer.value));
    await questions.getByLabel('Пояснение', { exact: true }).fill(answer.comment);
    await questions.getByRole('button', { name: 'Отправить ответ', exact: true }).click();
  });
  await step('Одобрение после ответа без перезагрузки', async () => {
    await assertOffer(page, customer.demo.expected.after_info!.offer);
  });
});
