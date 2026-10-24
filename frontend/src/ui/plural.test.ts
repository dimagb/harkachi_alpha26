import { expect, it } from 'vitest';
import { plural } from './plural';

it.each([[1, '1 балл'], [2, '2 балла'], [5, '5 баллов'], [11, '11 баллов'], [21, '21 балл'], [54, '54 балла'], [100, '100 баллов']])('склоняет оценку %i', (value, expected) => {
  expect(plural(Number(value), ['балл', 'балла', 'баллов'])).toBe(expected);
});
