import { createTheme, type MantineColorsTuple } from '@mantine/core';

// Кредитный кабинет предпринимателя — тема Mantine 9 из дизайн-токенов v1.
// Индекс 6 — базовый цвет, 7 — hover / текст бейджа, 0 — фон бейджа, 2 — рамка бейджа.

const signal: MantineColorsTuple = [
  '#FEF4F2', '#FFE7E3', '#FFCDC6', '#FEA69A', '#FF7264',
  '#F2443A', '#DC2C26', '#C42621', '#AD211C', '#8A1814',
];
const ok: MantineColorsTuple = [
  '#EFFAF3', '#DCF4E5', '#B9E8CB', '#8CD4A9', '#61BA88',
  '#3AA36D', '#1E8E5A', '#17704A', '#005330', '#003E23',
];
const wait: MantineColorsTuple = [
  '#FEF5E8', '#FEECD0', '#FFD79B', '#FFC25A', '#F5AF20',
  '#DF9D08', '#B78006', '#8B6001', '#6D4B04', '#513807',
];
const flow: MantineColorsTuple = [
  '#F4F7FA', '#E7EEF4', '#CFDCEA', '#B0C3D7', '#91A7BE',
  '#6F869E', '#4A6178', '#3E5368', '#2F4155', '#223042',
];
const stop: MantineColorsTuple = [
  '#FFF4F2', '#FFE6E2', '#FECDC5', '#FEA799', '#F27A6B',
  '#D64A3C', '#B42318', '#9A1D14', '#7D150E', '#600F09',
];
// Нейтральная шкала заменяет стандартный gray: 1 — surface, 2 — line, 5 — рамка поля, 7 — ink-2, 9 — ink.
const gray: MantineColorsTuple = [
  '#F7F8F9', '#F2F3F5', '#E4E6EA', '#CDD1D7', '#A9AFB7',
  '#8A919B', '#6A7280', '#535C68', '#3A3F47', '#1F2329',
];

export const theme = createTheme({
  primaryColor: 'signal',
  primaryShade: 6,
  colors: { signal, ok, wait, flow, stop, gray },
  white: '#FFFFFF',
  black: '#1F2329',
  autoContrast: true,
  luminanceThreshold: 0.35,

  fontFamily: "'Onest', system-ui, -apple-system, 'Segoe UI', sans-serif",
  fontFamilyMonospace: "ui-monospace, 'Cascadia Mono', Consolas, 'SF Mono', Menlo, monospace",
  fontSmoothing: true,
  fontSizes: { xs: '12px', sm: '14px', md: '16px', lg: '20px', xl: '24px' },
  lineHeights: { xs: '1.334', sm: '1.43', md: '1.5', lg: '1.4', xl: '1.334' },
  headings: {
    fontFamily: "'Onest', system-ui, -apple-system, 'Segoe UI', sans-serif",
    fontWeight: '600',
    textWrap: 'pretty',
    sizes: {
      h1: { fontSize: '32px', lineHeight: '40px', fontWeight: '600' },
      h2: { fontSize: '24px', lineHeight: '32px', fontWeight: '600' },
      h3: { fontSize: '20px', lineHeight: '28px', fontWeight: '600' },
      h4: { fontSize: '16px', lineHeight: '24px', fontWeight: '600' },
      h5: { fontSize: '14px', lineHeight: '20px', fontWeight: '600' },
      h6: { fontSize: '12px', lineHeight: '16px', fontWeight: '500' },
    },
  },

  spacing: {
    '2xs': '4px', xs: '8px', sm: '12px', md: '16px', lg: '24px', xl: '32px', '2xl': '48px',
  },
  radius: { xs: '4px', sm: '6px', md: 'var(--cc-radius-md)', lg: '16px', xl: '999px' },
  defaultRadius: 'sm',
  shadows: {
    xs: 'none',
    sm: '0 0 0 1px rgba(31, 35, 41, 0.08), 0 4px 12px rgba(31, 35, 41, 0.10)',
    md: '0 0 0 1px rgba(31, 35, 41, 0.08), 0 4px 12px rgba(31, 35, 41, 0.10)',
    lg: '0 0 0 1px rgba(31, 35, 41, 0.06), 0 16px 40px rgba(31, 35, 41, 0.18)',
    xl: '0 0 0 1px rgba(31, 35, 41, 0.06), 0 16px 40px rgba(31, 35, 41, 0.18)',
  },
  focusRing: 'auto',
  cursorType: 'pointer',

  other: {
    surface: '#F2F3F5',
    line: '#E4E6EA',
    lineInput: '#8A919B',
    inkDisabled: '#8A919B',
    displaySize: { fontSize: '40px', lineHeight: '48px', fontWeight: 600, letterSpacing: '-0.02em' },
    stage: { node: '24px', line: '2px', halo: '4px', lineRadius: '1px', waitMarker: '#F5AF20' },
    durationFast: '120ms',
    durationStage: '320ms',
    ease: 'cubic-bezier(0.2, 0, 0, 1)',
    money: (v: number) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(v) + '\u00A0₽',
  },

  components: {
    Card: { defaultProps: { radius: 'md', withBorder: true, shadow: 'xs', padding: 'lg' } },
    Paper: { defaultProps: { radius: 'md', shadow: 'xs' } },
    Menu: { defaultProps: { shadow: 'sm', radius: 'sm' } },
    Popover: { defaultProps: { shadow: 'sm', radius: 'sm' } },
    Modal: { defaultProps: { shadow: 'lg', radius: 'lg', overlayProps: { backgroundOpacity: 0.48, color: '#1F2329' } } },
    Badge: { defaultProps: { radius: 'sm', variant: 'light' }, styles: { root: { textTransform: 'none', fontWeight: 500 } } },
    Button: { defaultProps: { radius: 'sm' } },
  },
});
