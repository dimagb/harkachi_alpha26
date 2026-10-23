import { describe, expect, it } from 'vitest';
import { theme } from './theme';

describe('Тема кредитного кабинета', () => {
  it('использует сигнальный цвет для главного действия', () => {
    expect(theme.primaryColor).toBe('signal');
  });

  it.each([
    ['signal', 6, '#DC2C26'],
    ['ok', 6, '#1E8E5A'],
    ['wait', 6, '#B78006'],
    ['flow', 6, '#4A6178'],
    ['stop', 6, '#B42318'],
    ['gray', 9, '#1F2329'],
  ] as const)('задаёт 10 оттенков и опорный цвет %s', (name, index, color) => {
    expect(theme.colors?.[name]).toHaveLength(10);
    expect(theme.colors?.[name]?.[index]).toBe(color);
  });

  it('использует Onest основным шрифтом', () => {
    expect(theme.fontFamily).toMatch(/^'Onest'/);
  });

  it('форматирует рубли с неразрывными пробелами', () => {
    const money: string = theme.other!.money(1500000);
    expect(money.replace(/\s/g, ' ')).toBe('1 500 000 ₽');
    expect(money).not.toContain(' ');
  });
});
