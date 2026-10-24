import { Badge, Button, Divider, Fieldset, Group, Loader, Notification, NumberInput, Paper, Select, SimpleGrid, Stack, Text, Textarea, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { api } from '../api/client';
import type { components } from '../api/schema';
import { useCompany } from '../company/CompanyContext';
import { purposeLabels } from '../ui/labels';
import { formatMoney, stageStatusColor } from '../ui/status';
import card from './application/Card.module.css';
import css from './NewApplication.module.css';

type Schema = components['schemas'];
type Product = Schema['Product'];
type Purpose = Schema['ApplicationCreate']['purpose'];
const purposes: Purpose[] = ['WORKING_CAPITAL', 'CASH_GAP', 'EQUIPMENT', 'OTHER'];
const date = (value: string) => new Date(value).toLocaleDateString('ru-RU', { timeZone: 'UTC' });
const rate = (value: number) => value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function NewApplication() {
  const { companyId } = useCompany();
  return <ApplicationSelection key={companyId} />;
}

function ApplicationSelection() {
  const { companyId, membership } = useCompany();
  const [purpose, setPurpose] = useState<Purpose | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const products = useQuery({ queryKey: ['products'], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/products', { signal });
    if (error || !data) throw new Error('Не удалось загрузить продукты.');
    return data;
  }, retry: false });

  if (!companyId) return <Text>Для вашей учётной записи пока нет компании.</Text>;
  if (product && purpose) return <ApplicationForm product={product} initialPurpose={purpose} onBack={() => setProduct(null)} />;
  return <div className={card.page}>
    <header className={card.header}><Text size="sm" c="dimmed">Получить финансирование · Шаг 1 из 2</Text><h1 className={css.heading}>Зачем нужны деньги?</h1><Text c="dimmed">Выберите цель — покажем подходящие продукты и условия.</Text></header>
    <SimpleGrid className={card.card} cols={{ base: 1, sm: 2 }} spacing="sm" style={{ display: 'grid' }}>
      {purposes.map((value) => <Button key={value} variant={purpose === value ? 'light' : 'default'} aria-pressed={purpose === value} onClick={() => setPurpose(value)} h="auto" py="lg" styles={{ label: { whiteSpace: 'normal' } }}>{purposeLabels[value]}</Button>)}
    </SimpleGrid>
    {products.isPending && <div className={card.card}><Group role="status"><Loader size="sm" /><Text>Загружаем продукты…</Text></Group></div>}
    {products.isError && <div className={card.card}><Text role="alert">Не удалось загрузить продукты. Попробуйте ещё раз.</Text><Button w="fit-content" variant="default" onClick={() => void products.refetch()}>Повторить</Button></div>}
    {purpose && products.data && !products.data.some((item) => item.purposes.includes(purpose)) && <div className={card.card}><Text>Для этой цели пока нет продуктов. Выберите другую цель.</Text><Button variant="default" w="fit-content" onClick={() => setPurpose(null)}>Изменить цель</Button></div>}
    {purpose && products.data && <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
      {products.data.filter((item) => item.purposes.includes(purpose)).map((item) => <Paper className={card.card} component="section" aria-label={item.name} key={item.code}>
        <Stack h="100%" gap="md">
          <Title order={2} size="h3">{item.name}</Title><Text c="dimmed">{item.description}</Text><Divider />
          <Text fw={600}>от {formatMoney(item.min_amount)} до {formatMoney(item.max_amount)}</Text>
          <Text>{item.code === 'OVERDRAFT' ? 'на 12 мес., лимит возобновляется' : `на ${item.min_term_months}–${item.max_term_months} мес.`}</Text>
          <Text>ставка от {rate(item.rate_from)}%</Text>
          <Text size="xs" c="dimmed">ключевая ставка ЦБ {rate(item.key_rate)}% на {date(item.key_rate_date)}</Text>
          {membership?.company.kind === 'OOO' && item.requires_guarantor_ooo && <Text size="sm">Нужно поручительство владельца</Text>}
          <Button className={card.cta} mt="auto" onClick={() => setProduct(item)}>Выбрать</Button>
        </Stack>
      </Paper>)}
    </SimpleGrid>}
  </div>;
}

function ApplicationForm({ product, initialPurpose, onBack }: { product: Product; initialPurpose: Purpose; onBack: () => void }) {
  const { companyId } = useCompany();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState<string | number>(product.min_amount);
  const [term, setTerm] = useState<string | null>(String(product.min_term_months));
  const [purpose, setPurpose] = useState<Purpose>(initialPurpose);
  const [purposeText, setPurposeText] = useState('');
  const [revenue, setRevenue] = useState<string | number>('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [calculationInput, setCalculationInput] = useState<Schema['CalculatorRequest'] | null>(null);
  const validAmount = typeof amount === 'number' && Number.isSafeInteger(amount) && amount >= product.min_amount && amount <= product.max_amount;
  const validTerm = !!term && Number.isInteger(Number(term)) && Number(term) >= product.min_term_months && Number(term) <= product.max_term_months;
  const profile = useQuery({ queryKey: ['company-profile', companyId], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/companies/{id}/profile', { params: { path: { id: companyId! } }, signal });
    if (error || !data) throw new Error('Реестр временно недоступен, попробуйте позже');
    return data;
  }, retry: false });
  const ready = profile.isSuccess && !profile.isFetching;

  useEffect(() => {
    if (!validAmount || !validTerm || !ready) return;
    const timeout = setTimeout(() => setCalculationInput({ product_code: product.code, amount: Number(amount), term_months: Number(term) }), 400);
    return () => clearTimeout(timeout);
  }, [amount, term, product.code, validAmount, validTerm, ready]);
  const currentCalculation = ready && validAmount && validTerm && calculationInput?.amount === amount && calculationInput?.term_months === Number(term);
  const calculator = useQuery({ queryKey: ['calculator', companyId, calculationInput], queryFn: async ({ signal }) => {
    const { data, error } = await api.POST('/calculator', { body: calculationInput!, signal });
    if (error || !data) throw new Error('Не удалось рассчитать платёж. Попробуйте ещё раз.');
    return data;
  }, enabled: currentCalculation, retry: false });

  const create = useMutation({ mutationFn: async (body: Schema['ApplicationCreate']) => {
    const result = await api.POST('/applications', { body });
    if (result.error) {
      const serverFields = result.error.error.details.fields;
      if (result.response.status === 422 && serverFields && typeof serverFields === 'object') {
        setFields(Object.fromEntries(Object.entries(serverFields).filter((entry): entry is [string, string] => typeof entry[1] === 'string')));
      } else setMessage(result.error.error.message);
      return null;
    }
    return result.data;
  }, onSuccess: (data) => {
    if (!data) return;
    void queryClient.invalidateQueries({ queryKey: ['applications', companyId] });
    void navigate(`/app/applications/${data.id}`);
  }, onError: () => setMessage('Не удалось создать заявку. Проверьте соединение и попробуйте ещё раз.') });

  function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready || create.isPending) return;
    const errors: Record<string, string> = {};
    if (!validAmount) errors.amount = `Укажите целую сумму от ${formatMoney(product.min_amount)} до ${formatMoney(product.max_amount)}.`;
    if (!validTerm) errors.term_months = 'Выберите срок в пределах продукта.';
    if (!product.purposes.includes(purpose)) errors.purpose = 'Выберите цель кредита.';
    if (typeof revenue !== 'number' || !Number.isSafeInteger(revenue) || revenue <= 0) errors.declared_revenue_year = 'Укажите выручку больше нуля в целых рублях.';
    if (purpose === 'OTHER' && (purposeText.trim().length < 10 || purposeText.length > 500)) errors.purpose_text = 'Опишите цель: от 10 до 500 символов.';
    setFields(errors); setMessage('');
    if (Object.keys(errors).length) return;
    create.mutate({ company_id: companyId!, product_code: product.code, amount: Number(amount), term_months: Number(term), purpose, ...(purpose === 'OTHER' ? { purpose_text: purposeText.trim() } : {}), declared_revenue_year: Number(revenue) });
  }

  return <div className={card.page}>
    <header className={card.header}><Text size="sm" c="dimmed">Получить финансирование · Шаг 2 из 2</Text><h1 className={css.heading}>Заявка на финансирование</h1><Text c="dimmed">{product.name} · Укажите сумму и оцените платёж.</Text></header>
    <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl" style={{ alignItems: 'start' }}>
      <Paper className={card.card} component="section" aria-label="Профиль компании"><Stack>
        <Title order={2} size="h3">Профиль компании</Title>
        {profile.isPending && <Group role="status"><Loader size="sm" /><Text>Загружаем сведения…</Text></Group>}
        {profile.isError && <><Text role="alert">Реестр временно недоступен, попробуйте позже</Text><Button variant="default" loading={profile.isFetching} onClick={() => void profile.refetch()}>Повторить</Button></>}
        {profile.data && !profile.isError && <>
          <Text fw={600}>{profile.data.name}</Text>
          <Stack gap="xs"><Text size="sm">ИНН</Text><Text>{profile.data.inn}</Text><Text size="sm">ОГРН</Text><Text>{profile.data.ogrn}</Text></Stack>
          <Text>Дата регистрации: {date(profile.data.reg_date)}</Text><Text>ОКВЭД: {profile.data.okved_main}</Text><Text>Адрес: {profile.data.address}</Text><Text>Руководитель: {profile.data.director_full_name}</Text>
          <Divider /><Text fw={600}>Учредители</Text>
          {profile.data.founders.length ? profile.data.founders.map((founder, index) => <Text key={`${founder.full_name}-${index}`}>{founder.full_name} — {founder.share_pct}%</Text>) : <Text c="dimmed">Для ИП учредители не указываются.</Text>}
          <Text size="xs" c="dimmed">{profile.data.source_note}</Text>
        </>}
      </Stack></Paper>
      <Paper className={card.card} component="form" aria-label="Параметры заявки" onSubmit={submit} noValidate><Stack>
        <Title order={2} size="h3">Параметры заявки</Title>
        <Fieldset variant="unstyled" disabled={!ready || create.isPending}><Stack>
          <NumberInput label="Сумма, ₽" value={amount} onChange={setAmount} min={product.min_amount} max={product.max_amount} step={10000} thousandSeparator=" " allowDecimal={false} clampBehavior="none" error={fields.amount} />
          <Select label="Срок, мес." value={term} onChange={setTerm} allowDeselect={false} disabled={product.code === 'OVERDRAFT'} data={Array.from({ length: product.max_term_months - product.min_term_months + 1 }, (_, index) => String(product.min_term_months + index))} error={fields.term_months} />
          <Select label="Цель" value={purpose} onChange={(value) => { const selected = product.purposes.find((item) => item === value); if (selected) setPurpose(selected); }} allowDeselect={false} data={product.purposes.map((value) => ({ value, label: purposeLabels[value] }))} error={fields.purpose} />
          {purpose === 'OTHER' && <Textarea label="Опишите цель" description={`${purposeText.length} / 500`} value={purposeText} onChange={(event) => setPurposeText(event.currentTarget.value)} minLength={10} maxLength={500} rows={3} error={fields.purpose_text} />}
          <NumberInput label="Выручка за год, ₽" value={revenue} onChange={setRevenue} min={1} allowDecimal={false} thousandSeparator=" " clampBehavior="none" description={profile.data ? `По оборотам в нашем банке — около ${formatMoney(profile.data.avg_monthly_turnover * 12)}` : undefined} error={fields.declared_revenue_year} />
        </Stack></Fieldset>
        <Divider />
        <Stack gap="xs" aria-live="polite">
          <Badge color={stageStatusColor('current')} variant="light" w="fit-content">Расчёт платежа</Badge>
          {currentCalculation && calculator.data ? <>
            {calculator.data.monthly_payment === null ? <Text fw={600}>Проценты — только за использованные дни</Text> : <Text fw={600}>Платёж в месяц ≈ {formatMoney(calculator.data.monthly_payment)}</Text>}
            <Text>Ставка ≈ {rate(calculator.data.rate_estimate)}%</Text>
          </> : ready && validAmount && validTerm && !calculator.isError ? <Group role="status"><Loader size="xs" /><Text size="sm">Рассчитываем платёж…</Text></Group> : null}
          {currentCalculation && calculator.isError && <Notification color={stageStatusColor('failed')} withCloseButton={false}><Text>Не удалось рассчитать платёж. Попробуйте ещё раз.</Text><Button size="xs" variant="default" onClick={() => void calculator.refetch()}>Повторить расчёт</Button></Notification>}
          <Text size="xs" c="dimmed">Предварительный расчёт. Точные условия — после проверки заявки</Text>
        </Stack>
        {message && <Notification role="alert" color={stageStatusColor('failed')} withCloseButton={false}>{message}</Notification>}
        <Button className={card.cta} type="submit" disabled={!ready} loading={create.isPending}>Создать заявку</Button>
        <Button variant="default" onClick={onBack} disabled={create.isPending} styles={{ label: { whiteSpace: 'normal' } }} h="auto" py="sm">Назад к выбору продукта</Button>
      </Stack></Paper>
    </SimpleGrid>
  </div>;
}
