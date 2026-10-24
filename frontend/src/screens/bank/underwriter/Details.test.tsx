import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { BankDecision } from '../labels';
import { Rules } from './Details';

afterEach(cleanup);

it('показывает русское название правила, второстепенный код в конце и отдельные факт и порог', () => {
  const decision: BankDecision = {
    id: 'decision-1', kind: 'AUTO', outcome: 'DECLINE', created_at: '2026-10-25T00:00:00Z',
    config_version: '1', key_rate: 16, made_by: null, comment: null, client_reason_code: null,
    factors: [], grade: null, score: null, policy: null, recommendation: null, route_reason: null, what_if: [],
    rules_fired: [{ code: 'SF_OVERDUE', title: 'Есть текущая просрочка', value: '35 000 ₽; максимум 45 дн.', threshold: 'Не более 30 дней', effect: 'STOP' }],
    internal_reasons: [],
  };
  render(<Rules decision={decision} />);
  const title = screen.getByText('Есть текущая просрочка');
  expect(title.tagName).toBe('STRONG');
  expect(title.title).toBe('SF_OVERDUE');
  const code = screen.getByText('SF_OVERDUE');
  expect(code.closest('strong')).toBeNull();
  expect(code.parentElement?.lastElementChild).toBe(code);
  expect(screen.getByText('Факт: 35 000 ₽; максимум 45 дн.')).toBeTruthy();
  expect(screen.getByText('Порог: Не более 30 дней')).toBeTruthy();
});
