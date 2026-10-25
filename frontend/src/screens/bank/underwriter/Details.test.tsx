import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { BankDecision } from '../labels';
import { Rules } from './Details';

afterEach(cleanup);

it('показывает русское название правила, код только в подсказке и отдельные факт и порог', () => {
  const decision: BankDecision = {
    id: 'decision-1', kind: 'AUTO', outcome: 'DECLINE', created_at: '2026-10-25T00:00:00Z',
    config_version: '1', key_rate: 16, made_by: null, comment: null, client_reason_code: null,
    factors: [], grade: null, score: null, policy: null, recommendation: null, route_reason: null, what_if: [],
    rules_fired: [{ code: 'SF_OVERDUE', title: 'Есть текущая просрочка', value: '35 000 ₽; максимум 45 дн.', threshold: 'Не более 30 дней', effect: 'STOP' }],
    internal_reasons: ['SF_OVERDUE'],
  };
  render(<Rules decision={decision} />);
  const title = screen.getByText('Есть текущая просрочка');
  expect(title.tagName).toBe('STRONG');
  expect(title.title).toBe('SF_OVERDUE');
  expect(screen.queryByText('SF_OVERDUE')).toBeNull();
  expect(screen.getAllByText('Есть текущая просрочка')).toHaveLength(1);
  expect(screen.getByText('Факт: 35 000 ₽; максимум 45 дн.')).toBeTruthy();
  expect(screen.getByText('Порог: Не более 30 дней')).toBeTruthy();
});

it('показывает внутренние причины без правил русскими названиями', () => {
  const decision: BankDecision = {
    id: 'decision-2', kind: 'AUTO', outcome: 'MANUAL', created_at: '2026-10-25T00:00:00Z',
    config_version: '1', key_rate: 16, made_by: null, comment: null, client_reason_code: null,
    factors: [], grade: null, score: null, policy: null, recommendation: null, route_reason: null, what_if: [],
    rules_fired: [], internal_reasons: ['SF_ADDITIONAL', 'GRADE_C'],
  };
  render(<Rules decision={decision} />);
  expect(screen.getByTitle('SF_ADDITIONAL').textContent).toBe('Дополнительные проверки');
  expect(screen.getByTitle('GRADE_C').textContent).toBe('Пограничная оценка');
  expect(screen.queryByText(/SF_|GRADE_/)).toBeNull();
});

it.each([
  ['SF_INACTIVE', 'Компания не действует'],
  ['SF_BANKRUPTCY', 'Процедура банкротства'],
  ['SF_AGE', 'Недостаточный срок бизнеса'],
  ['SF_OVERDUE', 'Просроченная задолженность'],
  ['SF_TAX_DEBT', 'Налоги и обязательства'],
  ['SF_OKVED', 'Вид деятельности не подходит'],
  ['LOW_SCORE', 'Недостаточная оценка финансовых показателей'],
  ['HIGH_LOAD', 'Высокая долговая нагрузка'],
  ['VAL_REVENUE_MISMATCH', 'Нужно подтвердить выручку'],
  ['VAL_PURPOSE_UNCLEAR', 'Нужно описать цель'],
])('сохраняет смысл причины %s, когда в решении нет правила с названием', (code, title) => {
  const decision: BankDecision = {
    id: 'reason-only', kind: 'AUTO', outcome: 'DECLINE', created_at: '2026-10-25T00:00:00Z',
    config_version: '1', key_rate: 14, made_by: null, comment: null, client_reason_code: null,
    factors: [], grade: null, score: null, policy: null, recommendation: null, route_reason: null, what_if: [],
    rules_fired: [], internal_reasons: [code],
  };
  render(<Rules decision={decision} />);
  expect(screen.getByTitle(code).textContent).toBe(title);
});
