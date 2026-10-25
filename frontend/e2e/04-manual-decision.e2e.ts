import { test, expect, persona, createApplication, submitApplication, assertOffer, approve } from './helpers';
import type { Page } from '@playwright/test';

// Ловит неработающее ручное решение и утечку внутреннего комментария клиенту.
test('04 ooo_border — ручное решение андеррайтера', async ({ page, actor, step }) => {
  const customer = persona('ooo_border');
  const recommendation = customer.demo.expected.recommendation!;
  const comment = 'Проверено, одобряю по рекомендации — внутренний комментарий F-09';
  let id: string;
  let bank: Page;
  await step('Подача и ожидание специалиста', async () => {
    id = await createApplication(page, customer);
    await submitApplication(page, customer);
    await expect(page.getByRole('region', { name: 'Что происходит с заявкой', exact: true })).toContainText('Заявку рассматривает специалист', { timeout: 60_000 });
    await expect(page.getByRole('button', { name: 'Принять предложение', exact: true })).toHaveCount(0);
  });
  await step('Банк открывает собственный id, проверяет факторы и первоисточник', async () => {
    bank = await actor('underwriter');
    await bank.goto(`/bank/applications/${id}`);
    const factors = bank.getByRole('region', { name: 'Факторы оценки', exact: true });
    await expect(factors).toContainText(`Итого ${recommendation.score} / 100`);
    await expect(factors).toContainText(`Класс ${recommendation.grade}`);
    const buttons = factors.getByRole('button');
    await expect(buttons).toHaveCount(Object.keys(recommendation.points).length);
    await buttons.first().click();
    const source = factors.getByRole('region', { name: /^Первоисточник:/ });
    await expect(source).toBeVisible();
    await expect(source).toContainText('ЕГРЮЛ/ЕГРИП');
    await expect(source).toContainText('Дата регистрации');
    await expect(source).toContainText(/Получено \d{2}\.\d{2} \d{2}:\d{2}/);
    await expect(source).toContainText('Правило начисления');
  });
  await step('Одобрение с комментарием и оферта клиенту', async () => {
    await approve(bank, comment);
    await assertOffer(page, recommendation.offer);
    await expect(page.locator('body')).not.toContainText(comment);
    await expect(page.locator('body')).not.toContainText(/балл|класс|GRADE_/i);
  });
});
