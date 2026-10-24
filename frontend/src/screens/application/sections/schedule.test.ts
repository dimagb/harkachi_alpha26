import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { calculateSchedule } from './schedule';

it('закрывает эталонный кредит за 24 платежа с целыми рублями', () => {
  const data = JSON.parse(readFileSync('../contracts/personas.json', 'utf8')) as { personas: { code: string; demo: { expected: { offer: { amount: number; rate: number; term_months: number; monthly_payment: number } } } }[] };
  const offer = data.personas.find((p) => p.code === 'ip_good')!.demo.expected.offer;
  const rows = calculateSchedule(offer.amount, offer.rate, offer.term_months, '2026-10-24T09:00:00Z');
  expect(rows).toHaveLength(24);
  expect(rows[0]).toEqual({ number: 1, date: '2026-11-24', payment: 77817, interest: 27500, principal: 50317, balance: 1449683 });
  expect(rows[0]!.payment).toBe(offer.monthly_payment);
  expect(rows.reduce((sum, row) => sum + row.principal, 0)).toBe(1500000);
  expect(rows.at(-1)!.balance).toBe(0);
  expect(rows.every((row) => Number.isSafeInteger(row.payment) && row.payment === row.principal + row.interest && row.balance >= 0)).toBe(true);
});
it('даты от конца месяца не перепрыгивают через февраль и не накапливают сдвиг', () => {
  const rows = calculateSchedule(100000, 0, 3, '2028-01-31T12:00:00Z');
  expect(rows.map((row) => row.date)).toEqual(['2028-02-29', '2028-03-31', '2028-04-30']);
  expect(rows.map((row) => row.payment)).toEqual([33333, 33333, 33334]);
});
it('считает график от московской даты выдачи в 01:30 МСК', () => {
  const rows = calculateSchedule(100000, 0, 2, '2026-10-23T22:30:00Z');
  expect(rows.map((row) => row.date)).toEqual(['2026-11-24', '2026-12-24']);
});
