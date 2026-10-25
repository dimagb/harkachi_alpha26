import { Button, NumberInput, SegmentedControl, Select, Textarea } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { api } from '../../../api/client';
import { formatMoney } from '../../../ui/status';
import { outcomeLabels, reasonCategories, type BankApplication, type BankDecision, type DecisionRequest } from '../labels';
import css from './Underwriter.module.css';

export default function DecisionForm({ application, decision, onConflict }: { application: BankApplication; decision?: BankDecision; onConflict: () => void }) {
  const queryClient = useQueryClient();
  const recommendation = decision?.recommendation;
  const [outcome, setOutcome] = useState<DecisionRequest['outcome']>(recommendation?.outcome ?? 'APPROVE');
  const [amount, setAmount] = useState<number | string>(recommendation?.amount ?? application.amount);
  const [term, setTerm] = useState<number | string>(recommendation?.term_months ?? application.term_months);
  const [category, setCategory] = useState<NonNullable<DecisionRequest['client_reason_category']> | null>(null);
  const [questions, setQuestions] = useState(['']);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState('');
  const mobile = useMediaQuery('(max-width: 40em)');
  const products = useQuery({ queryKey: ['products'], queryFn: async ({ signal }) => { const { data, error } = await api.GET('/products', { signal }); if (error || !data) throw new Error('Не удалось загрузить границы продукта'); return data; } });
  const product = products.data?.find(p => p.code === application.product_code);
  const financed = outcome === 'APPROVE' || outcome === 'COUNTER';
  const stops = decision?.rules_fired.filter(rule => rule.effect === 'STOP') ?? [];
  const selectedAmount = outcome === 'APPROVE' ? application.amount : amount;
  const selectedTerm = outcome === 'APPROVE' ? application.term_months : term;
  const missing: string[] = [];
  if (comment.trim().length < 5 || comment.length > 2000) missing.push('Комментарий: от 5 до 2000 символов');
  if (financed) {
    if (!product) missing.push('Дождитесь загрузки границ продукта');
    else {
      if (typeof selectedAmount !== 'number' || !Number.isInteger(selectedAmount) || selectedAmount < product.min_amount || selectedAmount > product.max_amount) missing.push(`Сумма: от ${formatMoney(product.min_amount)} до ${formatMoney(product.max_amount)}`);
      if (typeof selectedTerm !== 'number' || !Number.isInteger(selectedTerm) || selectedTerm < product.min_term_months || selectedTerm > product.max_term_months) missing.push(`Срок: от ${product.min_term_months} до ${product.max_term_months} мес.`);
    }
  }
  if (outcome === 'DECLINE' && !category) missing.push('Выберите причину для клиента');
  if (outcome === 'COUNTER' && amount === application.amount && term === application.term_months) missing.push('Встречное предложение должно отличаться от заявки по сумме или сроку');
  if (outcome === 'REQUEST_INFO' && questions.some(q => q.trim().length < 5 || q.length > 500)) missing.push('Каждый вопрос: от 5 до 500 символов');
  const mismatch = !!recommendation && (outcome !== recommendation.outcome || financed && (selectedAmount !== recommendation.amount || selectedTerm !== recommendation.term_months));
  const options: DecisionRequest['outcome'][] = ['APPROVE', 'COUNTER', 'DECLINE', 'REQUEST_INFO'];
  if (decision?.route_reason === 'SOURCE_UNAVAILABLE') options.push('RETRY_ENRICHMENT');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (missing.length || loading) return;
    const body: DecisionRequest = { outcome, comment };
    if (financed) { body.amount = Number(selectedAmount); body.term_months = Number(selectedTerm); }
    if (outcome === 'DECLINE' && category) body.client_reason_category = category;
    if (outcome === 'REQUEST_INFO') body.info_questions = questions;
    setLoading(true); setFieldErrors({}); setFailure('');
    try {
      const { data, error, response } = await api.POST('/underwriting/{id}/decision', { params: { path: { id: application.id } }, body });
      if (response.status === 409) { onConflict(); return; }
      if (error || !data) {
        const fields = error?.error.details.fields;
        if (fields && typeof fields === 'object') setFieldErrors(Object.fromEntries(Object.entries(fields).filter((entry): entry is [string, string] => typeof entry[1] === 'string')));
        setFailure(error?.error.message ?? 'Не удалось принять решение. Повторите отправку.');
        return;
      }
      queryClient.setQueryData(['bank', 'application', application.id], data);
      await queryClient.invalidateQueries({ queryKey: ['bank', 'queue'] });
      notifications.show({ title: 'Решение принято', message: 'Результат сохранён в протоколе', color: 'ok' });
    } catch { setFailure('Не удалось принять решение. Проверьте соединение и повторите отправку.'); }
    finally { setLoading(false); }
  }

  return <section className={css.formSection} aria-label="Решение"><h2>Решение</h2><form onSubmit={event => void submit(event)} className={css.form}>
    <SegmentedControl classNames={{ root: css.decisionSwitch, label: css.decisionOption }} value={outcome} onChange={value => { setOutcome(value as DecisionRequest['outcome']); setFieldErrors({}); }} orientation={mobile || options.length > 4 ? 'vertical' : 'horizontal'} data={options.map(value => ({ value, label: outcomeLabels[value] }))} disabled={loading} />
    {financed && <div className={css.formNumbers}><NumberInput label="Сумма, ₽" value={selectedAmount} onChange={setAmount} readOnly={outcome === 'APPROVE'} min={product?.min_amount} max={product?.max_amount} clampBehavior="none" allowDecimal={false} allowNegative={false} thousandSeparator=" " hideControls error={fieldErrors.amount} /><NumberInput label="Срок, мес." value={selectedTerm} onChange={setTerm} readOnly={outcome === 'APPROVE'} min={product?.min_term_months} max={product?.max_term_months} clampBehavior="none" allowDecimal={false} allowNegative={false} hideControls error={fieldErrors.term_months} /></div>}
    {products.isError && financed && <div role="alert">Не удалось загрузить границы продукта. <Button variant="subtle" onClick={() => void products.refetch()}>Повторить</Button></div>}
    {outcome === 'DECLINE' && <Select label="Причина для клиента" placeholder="Выберите категорию" value={category} onChange={value => setCategory(reasonCategories.find(c => c === value) ?? null)} data={reasonCategories} error={fieldErrors.client_reason_category} description="Клиент увидит только категорию, без баллов" />}
    {outcome === 'REQUEST_INFO' && <div className={css.questions}><span className={css.caption}>Вопросы клиенту · {questions.length} из 5</span>{questions.map((question, i) => <div className={css.question} key={i}><Textarea label={`Вопрос ${i + 1}`} value={question} onChange={event => setQuestions(previous => previous.map((q, index) => index === i ? event.target.value : q))} minRows={2} autosize maxLength={500} error={fieldErrors[`info_questions.${i}`] ?? fieldErrors[`info_questions[${i}]`]} /><Button variant="subtle" color="gray" aria-label={`Удалить вопрос ${i + 1}`} disabled={questions.length === 1} onClick={() => setQuestions(previous => previous.filter((_, index) => index !== i))}>×</Button></div>)}<Button variant="default" onClick={() => setQuestions(previous => [...previous, ''])} disabled={questions.length >= 5}>Добавить вопрос</Button>{fieldErrors.info_questions && <p className={css.error}>{fieldErrors.info_questions}</p>}</div>}
    <Textarea classNames={{ label: css.fieldLabel, input: css.commentInput }} label="Комментарий (обязательно)" value={comment} onChange={event => setComment(event.target.value)} minRows={3} maxLength={2000} autosize placeholder="Обоснование решения для протокола" error={fieldErrors.comment} />
    {mismatch && <div className={css.warning} role="status">Решение не совпадает с рекомендацией — это будет отмечено в журнале</div>}
    {financed && stops.map((rule, index) => <div key={`${rule.code}-${index}`} className={css.warning} role="status">Есть стоп-фактор: {rule.title}. Решение вопреки стоп-фактору будет отмечено в истории заявки</div>)}
    {failure && <p role="alert" className={css.error}>{failure}</p>}{fieldErrors.outcome && <p className={css.error}>{fieldErrors.outcome}</p>}
    <Button type="submit" className={css.submit} fullWidth disabled={!!missing.length || loading} loading={loading}>Принять решение</Button>
    {!!missing.length && <div className={css.hint}>{missing.join('. ')}</div>}
  </form></section>;
}
