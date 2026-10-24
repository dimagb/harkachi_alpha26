import { Select } from '@mantine/core';
import { stateLabels, type BankApplication } from '../labels';

type State = BankApplication['state'];
const groups: { group: string; states: State[] }[] = [
  { group: 'Заявка', states: ['DRAFT', 'SUBMITTED'] },
  { group: 'Проверка данных', states: ['VALIDATION', 'ENRICHMENT', 'INFO_REQUESTED'] },
  { group: 'Оценка', states: ['ASSESSMENT', 'MANUAL_REVIEW'] },
  { group: 'Решение', states: ['OFFER_ISSUED', 'DECLINED', 'WITHDRAWN', 'EXPIRED'] },
  { group: 'Подписание', states: ['SIGNING', 'SIGNED'] },
  { group: 'Выдача', states: ['DISBURSED'] },
];
export default function StateFilter({ value, onChange }: { value: State | null; onChange: (state: State | null) => void }) {
  return <Select label="Этап" value={value ?? 'ALL'} onChange={state => onChange(state === 'ALL' || !state ? null : state as State)} allowDeselect={false} comboboxProps={{ withinPortal: false }} data={[
    { value: 'ALL', label: 'Все' },
    ...groups.map(({ group, states }) => ({ group, items: states.map(state => ({ value: state, label: stateLabels[state] })) })),
  ]} />;
}
