import { MantineProvider } from '@mantine/core';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import Login from './Login';
import alfaLogo from './assets/alfa-logo.svg';

afterEach(cleanup);

it('показывает логотип Альфа-Банка над формой входа', () => {
  render(<MantineProvider env="test"><Login /></MantineProvider>);
  const logo = screen.getByRole('img', { name: 'Альфа-Банк' });
  const form = screen.getByRole('region', { name: 'Вход в кабинет' });
  expect(logo.getAttribute('src')).toBe(`${alfaLogo}#svgView(viewBox(152,97,189,288))`);
  expect(logo.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it('показывает подвал прототипа после формы и демо-учёток', () => {
  render(<MantineProvider env="test"><Login /></MantineProvider>);
  const footer = screen.getByRole('contentinfo');
  expect(footer.textContent).toContain('Данные синтетические');
  expect(screen.getByRole('region', { name: 'Демо-учётки' }).compareDocumentPosition(footer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
