import { describe, expect, it } from 'vitest';
import type { components } from '../api/schema';
import { formatMoney, stageStatusColor, stageStatusIcon } from './status';

describe('Цвет этапа заявки', () => {
  const cases = [
    ['done', 'ok'],
    ['current', 'gray'],
    ['action_required', 'wait'],
    ['failed', 'stop'],
    ['cancelled', 'gray'],
    ['pending', 'gray'],
  ] as const satisfies ReadonlyArray<
    readonly [components['schemas']['TimelineItem']['status'], string]
  >;

  it.each(cases)('%s отображается цветом %s', (status, color) => {
    expect(stageStatusColor(status)).toBe(color);
  });

  // @ts-expect-error — неизвестный статус запрещён контрактом; разрешено карточкой F-02.
  stageStatusColor('unknown');
});

it.each([['done', '✓'], ['current', 'number'], ['action_required', '!'], ['failed', '×'], ['cancelled', '×'], ['pending', 'number']] as const)('иконка %s: %s', (status, icon) => {
  expect(stageStatusIcon(status)).toBe(icon);
});

describe('Суммы в рублях', () => {
  it.each([
    [0, '0 ₽'],
    [1500000, '1 500 000 ₽'],
    [77817, '77 817 ₽'],
    [11111, '11 111 ₽'],
  ])('форматирует %i через тему', (value, expected) => {
    const money = formatMoney(value);
    expect(money.replace(/\s/g, ' ')).toBe(expected);
    expect(money).not.toContain(' ');
  });
});
