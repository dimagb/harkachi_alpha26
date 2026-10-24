import { Anchor, Button, Group, Loader, Modal, Notification, Stack, Text, Title, VisuallyHidden } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { api } from '../api/client';
import type { components } from '../api/schema';
import { stateLabels } from '../ui/labels';
import { formatMoney, stageStatusColor } from '../ui/status';
import Timeline from './application/Timeline';
import StatusPanel from './application/StatusPanel';
import KeyFigures from './application/KeyFigures';
import Details from './application/Details';
import History from './application/History';
import css from './application/Card.module.css';
import DecisionSection, { DecisionLinks } from './application/sections/DecisionSection';
import InfoRequestSection from './application/sections/InfoRequestSection';
import ObjectionBlock from './application/sections/ObjectionBlock';
import decisionCss from './application/sections/DecisionSection.module.css';

class CardError extends Error {
  constructor(readonly status: number) { super('Не удалось загрузить заявку. Попробуйте ещё раз.'); }
}
const polling = new Set(['SUBMITTED', 'VALIDATION', 'ENRICHMENT', 'ASSESSMENT', 'MANUAL_REVIEW', 'SIGNED']);
type CardProps = { companies: components['schemas']['MeResponse']['companies']; userId: string };
export default function ApplicationCard({ companies, userId }: CardProps) {
  const { id = '' } = useParams();
  return <CardContent key={`${userId}:${id}`} id={id} companies={companies} userId={userId} />;
}
function CardContent({ id, companies, userId }: CardProps & { id: string }) {
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const [message, setMessage] = useState('');
  const application = useQuery({ queryKey: ['application', id, userId], queryFn: async ({ signal }) => {
    const { data, error, response } = await api.GET('/applications/{id}', { params: { path: { id } }, signal });
    if (error || !data) throw new CardError(response.status);
    return data;
  }, retry: false, refetchInterval: (query) => query.state.data && !query.state.error && polling.has(query.state.data.state) ? 2000 : false });
  const data = application.data;
  const products = useQuery({ queryKey: ['products'], queryFn: async ({ signal }) => {
    const { data, error } = await api.GET('/products', { signal });
    if (error || !data) throw new Error('Не удалось загрузить продукты.');
    return data;
  }, enabled: !!data, retry: false });
  const calculation = useQuery({ queryKey: ['card-calculator', id, userId], queryFn: async ({ signal }) => {
    const { data: estimate, error } = await api.POST('/calculator', { body: { product_code: data!.product_code, amount: data!.amount, term_months: data!.term_months }, signal });
    if (error || !estimate) throw new Error('Расчёт недоступен.');
    return estimate;
  }, enabled: !!data && !data.offer, retry: false, staleTime: Infinity, gcTime: 0, refetchOnWindowFocus: false, refetchOnReconnect: false });
  const profile = useQuery({ queryKey: ['company-profile', data?.company_id, userId], queryFn: async ({ signal }) => {
    const { data: company, error } = await api.GET('/companies/{id}/profile', { params: { path: { id: data!.company_id } }, signal });
    if (error || !company) throw new Error('Сведения о компании недоступны.');
    return company;
  }, enabled: !!data && companies.some(({ company }) => company.id === data.company_id), retry: false });
  const withdraw = useMutation({ mutationFn: async () => {
    const result = await api.POST('/applications/{id}/withdraw', { params: { path: { id } } });
    if (result.error) {
      setMessage(result.response.status === 409 ? 'Заявка уже изменилась' : result.error.error.message);
      if (result.response.status === 409) await application.refetch();
      return null;
    }
    return result.data;
  }, onSuccess: (updated) => {
    setConfirm(false);
    if (!updated) return;
    queryClient.setQueryData(['application', id, userId], updated);
    void queryClient.invalidateQueries({ queryKey: ['applications', updated.company_id] });
  }, onError: () => { setConfirm(false); setMessage('Не удалось отозвать заявку. Проверьте соединение и попробуйте ещё раз.'); } });

  const pageHeading = <VisuallyHidden><Title order={1}>Карточка заявки</Title></VisuallyHidden>;
  if (application.isPending) return <>{pageHeading}<Group role="status"><Loader size="sm" /><Text>Загружаем заявку…</Text></Group></>;
  if (application.error instanceof CardError && application.error.status === 404) return <Stack>{pageHeading}<Title order={2}>Заявка не найдена</Title><Anchor component={Link} to="/app">К моим заявкам</Anchor></Stack>;
  if (application.isError || !data || products.isError) return <Stack align="flex-start">{pageHeading}<Text role="alert">Не удалось загрузить заявку. Попробуйте ещё раз.</Text><Button variant="default" onClick={() => { void application.refetch(); if (products.isError) void products.refetch(); }}>Повторить</Button><Anchor component={Link} to="/app">К моим заявкам</Anchor></Stack>;
  const current = data.timeline.find((step) => step.stage_code === data.stage.code);
  const status = current?.status ?? 'pending';
  const offered = data.state === 'OFFER_ISSUED' && data.offer;
  const decisionHeading = offered ? data.offer!.kind === 'APPROVED' ? `Банк одобрил ${formatMoney(data.offer!.amount)}` : `Банк готов выдать ${formatMoney(data.offer!.amount)} на ${data.offer!.term_months} мес.` : data.state === 'DECLINED' ? 'Банк не может выдать кредит сейчас' : null;
  const product = products.data?.find((product) => product.code === data.product_code);
  const color = offered ? data.offer!.kind === 'APPROVED' ? 'ok' : 'wait' : data.state === 'DECLINED' ? 'stop' : stageStatusColor(status);
  const label = offered ? data.offer!.kind === 'APPROVED' ? 'Одобрено' : 'Другие условия' : data.state === 'DECLINED' ? 'Отказ' : data.state === 'WITHDRAWN' ? 'Отозвана' : stateLabels[data.state];
  const onUpdate = (updated: components['schemas']['ApplicationClient']) => {
    queryClient.setQueryData(['application', id, userId], updated);
    void queryClient.invalidateQueries({ queryKey: ['applications', updated.company_id] });
  };
  const sectionProps = { application: data, onUpdate, onReload: () => application.refetch(), onMessage: setMessage };
  return <div className={css.page} key={id}>
    {pageHeading}
    <header className={css.header}>
      <div className={css.meta}><span className={css.muted}>Заявка № {data.number}{decisionHeading && ` · ${product?.name ?? 'Загружаем продукт…'}`}</span><span className={css.badge} data-variant="light" style={{ background: `var(--mantine-color-${color}-0)`, borderColor: `var(--mantine-color-${color}-2)`, color: `var(--mantine-color-${color}-7)` }}><span aria-hidden="true" className={css.dot} style={{ background: `var(--mantine-color-${color}-${color === 'wait' ? 4 : color === 'gray' ? 9 : 6})` }} />{label}</span></div>
      {decisionHeading ? <h2 className={decisionCss.heading}>{decisionHeading}</h2> : <h2 className={css.heading}><span className={css.headingCopy}>{product?.name ?? 'Загружаем продукт…'} ·</span><span className={css.amount}>{formatMoney(data.offer?.amount ?? data.amount)}</span><span className={css.headingCopy}>на {data.offer?.term_months ?? data.term_months} мес.</span></h2>}
    </header>
    <div className={`${css.card} ${css.stageCard}`}><Timeline timeline={data.timeline} /><StatusPanel application={data} status={status} /></div>
    {message && <Notification role="alert" color="stop" withCloseButton={false}>{message}</Notification>}
    <DecisionSection {...sectionProps} userId={userId} product={product} companyKind={companies.find(({ company }) => company.id === data.company_id)?.company.kind} />
    <ObjectionBlock {...sectionProps} />
    {data.state === 'DECLINED' && <DecisionLinks application={data} />}
    {data.info_request && <InfoRequestSection key={data.info_request.id} {...sectionProps} />}
    <div className={css.columns}>
      <section className={css.card} aria-label="Параметры заявки"><h3 className={css.title}>Параметры заявки</h3><KeyFigures application={data} calculation={calculation.data} error={calculation.isError} onRetry={() => void calculation.refetch()} /><Details application={data} company={companies.find(({ company }) => company.id === data.company_id)?.company} sourceNote={profile.data?.source_note} />
        {data.allowed_actions.includes('WITHDRAW') && <div className={css.withdraw}><button type="button" className={css.textButton} onClick={() => { setMessage(''); setConfirm(true); }}>Отозвать заявку</button></div>}
      </section>
      <History timeline={data.timeline} />
    </div>
    {data.state !== 'DECLINED' && data.client_reason && <Text>{data.client_reason.text}</Text>}
    <section id="submit" /><section id="signing" />
    <Modal opened={confirm} onClose={() => { if (!withdraw.isPending) setConfirm(false); }} title={`Отозвать заявку № ${data.number}? Это действие нельзя отменить.`} centered>
      <Group justify="flex-end"><Button variant="default" disabled={withdraw.isPending} onClick={() => setConfirm(false)}>Не отзывать</Button><Button loading={withdraw.isPending} onClick={() => withdraw.mutate()}>Отозвать</Button></Group>
    </Modal>
  </div>;
}
