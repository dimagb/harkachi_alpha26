import { Button, NumberInput, Textarea } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../../api/client';
import type { components } from '../../../api/schema';
import card from '../Card.module.css';
import css from './InfoRequestSection.module.css';

type Application = components['schemas']['ApplicationClient'];
type Answer = components['schemas']['InfoResponseRequest']['answers'][number];
type Props = { application: Application; onUpdate: (application: Application) => void; onReload: () => Promise<unknown>; onMessage: (message: string) => void };
export default function InfoRequestSection({ application, onUpdate, onReload, onMessage }: Props) {
  const request = application.info_request!;
  const [answers, setAnswers] = useState(() => request.items.map((item) => ({ item_code: item.item_code, value: '' as number | string, comment: '' })));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const canAnswer = application.allowed_actions.includes('ANSWER_INFO_REQUEST');
  const send = useMutation({ mutationFn: async (body: { answers: Answer[] }) => {
    onMessage('');
    const result = await api.POST('/applications/{id}/info-response', { params: { path: { id: application.id } }, body });
    if (result.error) {
      if (result.response.status === 409) { onMessage('Запрос уже закрыт'); await onReload(); }
      else if (result.response.status === 422) {
        const fields = result.error.error.details.fields;
        const next: Record<string, string> = {};
        if (fields && typeof fields === 'object') for (const [key, value] of Object.entries(fields)) if (typeof value === 'string') next[key] = value;
        setErrors(next);
        if (!Object.keys(next).length) onMessage(result.error.error.message);
      } else onMessage(result.response.status === 501 ? 'Действие пока недоступно, попробуйте позже' : result.error.error.message);
    } else if (result.data) onUpdate(result.data);
  }, onError: () => onMessage('Не удалось отправить ответ. Проверьте соединение и попробуйте ещё раз.') });
  return <section id="info-request" aria-label="Вопросы банка" className={`${card.card} ${css.section}`}>
    <div><h3 className={card.title}>Вопросы банка</h3><p className={css.deadline}>Ответьте до {new Date(request.due_at).toLocaleDateString('ru-RU', { timeZone: 'Europe/Moscow' })}</p></div>
    <form noValidate className={css.form} onSubmit={(event) => {
      event.preventDefault();
      if (!canAnswer || send.isPending) return;
      const next: Record<string, string> = {};
      const payload: Answer[] = request.items.map((item, index) => {
        const answer = answers[index]!;
        if (item.requires_value && (typeof answer.value !== 'number' || !Number.isSafeInteger(answer.value) || answer.value <= 0)) next[`answers.${index}.value`] = 'Укажите целую выручку больше нуля';
        if (answer.comment.length < 3 || answer.comment.length > 1000 || answer.comment.trim().length < 3) next[`answers.${index}.comment`] = 'Введите от 3 до 1000 символов';
        return { item_code: item.item_code, ...(item.requires_value ? { value: Number(answer.value) } : {}), comment: answer.comment };
      });
      setErrors(next);
      if (!Object.keys(next).length) send.mutate({ answers: payload });
    }}>
      {request.items.map((item, index) => {
        const answer = answers[index]!;
        const update = (patch: Partial<typeof answer>) => setAnswers((previous) => previous.map((value, position) => position === index ? { ...value, ...patch } : value));
        return <fieldset key={`${index}:${item.item_code}`} className={css.question} disabled={send.isPending || !canAnswer}>
          <legend className={css.legend}>{item.question}</legend>
          {item.requires_value && <NumberInput label="Выручка за год, ₽" value={answer.value} onChange={(value) => update({ value })} thousandSeparator=" " allowDecimal={false} allowNegative={false} hideControls error={errors[`answers.${index}.value`]} />}
          <Textarea label={item.requires_value ? 'Пояснение' : 'Ответ'} value={answer.comment} onChange={(event) => update({ comment: event.currentTarget.value })} description={`${answer.comment.length} / 1000`} error={errors[`answers.${index}.comment`]} rows={3} />
        </fieldset>;
      })}
      {errors.answers && <p role="alert">{errors.answers}</p>}
      {canAnswer && <Button type="submit" loading={send.isPending} className={card.cta}>Отправить ответ</Button>}
    </form>
  </section>;
}
