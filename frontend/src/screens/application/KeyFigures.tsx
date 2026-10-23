import { Button, Paper, SimpleGrid, Stack, Text } from '@mantine/core';
import type { components } from '../../api/schema';
import { formatMoney } from '../../ui/status';
import type { Application } from './presentation';

export default function KeyFigures({ application, calculation, error, onRetry }: { application: Application; calculation?: components['schemas']['CalculatorResponse']; error: boolean; onRetry: () => void }) {
  const offer = application.offer;
  const rate = offer?.rate ?? calculation?.rate_estimate;
  const payment = offer ? offer.monthly_payment : calculation?.monthly_payment;
  const prefix = offer ? '' : 'около ';
  const figures = [
    ['Сумма', formatMoney(offer?.amount ?? application.amount)], ['Срок', `${offer?.term_months ?? application.term_months} мес.`],
    ['Ставка', rate === undefined ? 'Рассчитываем…' : `${prefix}${rate.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`],
    ['Платёж в месяц', payment === null ? 'Проценты — только за использованные дни' : payment === undefined ? 'Рассчитываем…' : `${prefix}${formatMoney(payment)}`],
  ];
  return <Stack component="section" aria-label="Ключевые цифры" gap="sm">
    <SimpleGrid cols={2} spacing="sm">{figures.map(([label, value]) => <Paper key={label} bg="gray.1" p="md" radius="md" style={{ minWidth: 0 }}><Stack gap={4}><Text size="sm" c="dimmed">{label}</Text><Text fw={600} fz={{ base: 18, sm: 26 }} style={{ overflowWrap: 'anywhere', fontVariantNumeric: 'tabular-nums' }}>{error && !offer && ['Ставка', 'Платёж в месяц'].includes(label!) ? 'Расчёт недоступен' : value}</Text></Stack></Paper>)}</SimpleGrid>
    {error && !offer && <><Text size="sm" role="alert">Не удалось рассчитать предварительные условия.</Text><Button variant="default" size="xs" onClick={onRetry}>Повторить расчёт</Button></>}
  </Stack>;
}
