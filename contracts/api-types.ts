/**
 * Строгий контракт API credit-core v1 — источник правды до появления contracts/openapi.json.
 *
 * Правила:
 * - Бэкенд повторяет эти типы в Pydantic v2 (extra="forbid"), фронтенд импортирует до генерации клиента.
 * - После 24.10 12:00 источник правды — contracts/openapi.json (снимок из кода); он обязан совпадать с этим файлом.
 * - Любое изменение — PR через тимлида. Перечисления — contracts/codes.md.
 * - Деньги — целые рубли (integer, без копеек; в БД bigint). Платёж округляется до рубля ROUND_HALF_UP; сумма встречного — вниз до 50 000.
 * - Ставки — число с 2 знаками (22.00 = 22%). Месяц — "YYYY-MM".
 * - Даты — ISO 8601: дата "YYYY-MM-DD", момент времени "YYYY-MM-DDTHH:mm:ssZ" (UTC).
 * - Поле, помеченное `?`, может отсутствовать; `| null` — присутствует, но может быть null.
 */

// ---------- Перечисления (= contracts/codes.md) ----------
export type Role = "CLIENT" | "UNDERWRITER" | "GUARANTOR";
export type CompanyKind = "IP" | "OOO";
export type ProductCode = "EXPRESS" | "WORKING_CAPITAL" | "OVERDRAFT";
export type Purpose = "WORKING_CAPITAL" | "CASH_GAP" | "EQUIPMENT" | "OTHER";
export type ApplicationState =
  | "DRAFT" | "SUBMITTED" | "VALIDATION" | "INFO_REQUESTED" | "ENRICHMENT" | "ASSESSMENT"
  | "MANUAL_REVIEW" | "OFFER_ISSUED" | "DECLINED" | "SIGNING" | "SIGNED" | "DISBURSED"
  | "WITHDRAWN" | "EXPIRED";
export type StageCode = "APPLICATION" | "CHECK" | "ASSESSMENT" | "DECISION" | "SIGNING" | "DISBURSEMENT";
export type StageStatus = "done" | "current" | "action_required" | "pending" | "failed" | "cancelled";
export type ClientAction =
  | "EDIT_DRAFT" | "SUBMIT" | "REQUEST_SIGNATURE" | "ANSWER_INFO_REQUEST" | "ACCEPT_OFFER"
  | "REJECT_OFFER" | "SIGN" | "WITHDRAW" | "OBJECT" | "NEW_APPLICATION";
export type InfoItemCode = "REVENUE_CONFIRM" | "PURPOSE_DETAILS" | "UNDERWRITER_QUESTION";
export type OfferKind = "APPROVED" | "COUNTER";
export type OfferStatus = "ACTIVE" | "ACCEPTED" | "REJECTED" | "EXPIRED" | "SUPERSEDED";
export type PartyRole = "BORROWER_SIGNATORY" | "GUARANTOR";
export type OtpPurpose = "CONSENTS" | "OFFER" | "GUARANTEE";
export type Grade = "A" | "B" | "C" | "D";
export type RouteReason =
  | "GRADE_C" | "AMOUNT_ABOVE_AUTO" | "NO_AUTO_CONSENT" | "SOURCE_UNAVAILABLE" | "OBJECTION" | "INFO_RESPONSE";
export type UnderwriterOutcome = "APPROVE" | "COUNTER" | "DECLINE" | "REQUEST_INFO" | "RETRY_ENRICHMENT";
export type ClientReasonCategory =
  | "Данные о компании" | "Финансовое положение" | "Срок ведения бизнеса" | "Кредитная история"
  | "Налоги и обязательства" | "Условия продукта" | "Дополнительные проверки"
  | "Финансовые показатели" | "Долговая нагрузка";
export type CheckSource = "BKI" | "EGRUL" | "FNS";
export type CheckStatus = "PENDING" | "OK" | "FAILED";

// ---------- Ошибки ----------
export type ErrorCode =
  | "VALIDATION_ERROR" | "UNAUTHORIZED" | "FORBIDDEN" | "NOT_FOUND" | "INVALID_TRANSITION"
  | "CONFLICT_VERSION" | "OFFER_EXPIRED" | "SIGN_NOT_ALLOWED" | "OTP_INVALID" | "OBJECTION_NOT_ALLOWED"
  | "SERVICE_UNAVAILABLE" | "INTERNAL_ERROR"
  | "NOT_IMPLEMENTED"; // 501 — только заглушки на время разработки; к 26.10 ни один путь из api.md не отвечает 501
export interface ApiError {
  error: { code: ErrorCode; message: string; details: Record<string, unknown> };
}
// HTTP: VALIDATION_ERROR 422, UNAUTHORIZED 401, FORBIDDEN/SIGN_NOT_ALLOWED/OBJECTION_NOT_ALLOWED 403,
// NOT_FOUND 404, INVALID_TRANSITION/CONFLICT_VERSION/OFFER_EXPIRED 409, OTP_INVALID 422,
// SERVICE_UNAVAILABLE 503 (/ready: БД недоступна), INTERNAL_ERROR 500 (необработанное исключение, без деталей наружу).
// Прочие HTTP-ошибки фреймворка (405 и т. п.) отдаются с ближайшим кодом: 405 → NOT_FOUND.
// details для VALIDATION_ERROR: { fields: { [field: string]: string /* текст для пользователя */ } }

// ---------- Аутентификация ----------
export interface LoginRequest { login: string; password: string } // POST /auth/login
export interface UserBrief { id: string; full_name: string; role: Role }
export interface LoginResponse { access_token: string; token_type: "bearer"; expires_in: number; user: UserBrief }
export interface CompanyBrief {
  id: string; inn: string; kind: CompanyKind; name: string;
}
export interface Membership { company: CompanyBrief; position: string; can_sign: boolean; is_founder: boolean }
export interface MeResponse { user: UserBrief; companies: Membership[] } // GET /me

// ---------- Каталог и калькулятор ----------
export interface Product { // GET /products → Product[]
  code: ProductCode; name: string; description: string; purposes: Purpose[];
  min_amount: number; max_amount: number; min_term_months: number; max_term_months: number;
  rate_from: number;            // КС + минимальный спред (A), справочно
  requires_guarantor_ooo: boolean;
  key_rate: number; key_rate_date: string;
}
export interface CalculatorRequest { product_code: ProductCode; amount: number; term_months: number } // POST /calculator
export interface CalculatorResponse { rate_estimate: number; monthly_payment: number | null /* null для OVERDRAFT */ }

// ---------- Профиль компании ----------
export interface CompanyProfile { // GET /companies/{id}/profile — только своей компании
  id: string; inn: string; ogrn: string; kind: CompanyKind; name: string;
  status: "ACTIVE" | "LIQUIDATING" | "LIQUIDATED"; reg_date: string; okved_main: string; address: string;
  director_full_name: string;
  founders: { full_name: string; share_pct: number }[];
  avg_monthly_turnover: number; // из оборотов банка, для подсказки в форме
  source_note: string;          // «Данные из ЕГРЮЛ на 23.10.2026»
}

// ---------- Заявка (клиент) ----------
export interface ApplicationCreate { // POST /applications
  company_id: string; product_code: ProductCode;
  amount: number;            // целые рубли, в пределах продукта
  term_months: number;       // в пределах продукта; для OVERDRAFT всегда 12
  purpose: Purpose;
  purpose_text?: string;     // обязательно при purpose = "OTHER", 10–500 символов
  declared_revenue_year: number; // > 0
}
export type ApplicationPatch = Partial<Omit<ApplicationCreate, "company_id">>; // PATCH, заголовок If-Match: <version>

export interface TimelineItem { stage_code: StageCode; title: string; status: StageStatus; at: string | null }
export interface Stage { index: 1 | 2 | 3 | 4 | 5 | 6; code: StageCode; title: string; what_happens: string; what_to_do: string | null }
export interface OfferClient {
  id: string; version: number; kind: OfferKind; status: OfferStatus; product_code: ProductCode;
  amount: number; term_months: number; rate: number;
  monthly_payment: number | null; // null для OVERDRAFT
  expires_at: string;
  explanation: string[];          // 1–3 клиентские формулировки сильных сторон, без баллов
  requested: { amount: number; term_months: number } | null; // для COUNTER — «вы просили»
  counter_reason: string | null;  // для COUNTER — почему условия изменены
}
export interface ClientReason {
  code: string;                   // клиентский код из codes.md (никогда SF_ADDITIONAL)
  category: ClientReasonCategory | null; // null для CLIENT_WITHDREW, CLIENT_REJECTED_OFFER, EXPIRED_*
  text: string; action: string | null; retry_after: string | null;
}
export interface InfoRequestItem { item_code: InfoItemCode; question: string; requires_value: boolean }
export interface InfoRequestClient { id: string; items: InfoRequestItem[]; due_at: string }
export interface PartyClient { id: string; role: PartyRole; full_name: string; signed: boolean /* = party.status === "SIGNED" */; is_me: boolean }
export interface ApplicationClient { // GET /applications/{id}; в списке — ApplicationListItem
  id: string; number: number; version: number; company_id: string; state: ApplicationState;
  stage: Stage; timeline: TimelineItem[];
  product_code: ProductCode; amount: number; term_months: number; purpose: Purpose; purpose_text: string | null;
  declared_revenue_year: number;
  offer: OfferClient | null; client_reason: ClientReason | null; info_request: InfoRequestClient | null;
  parties: PartyClient[];
  allowed_actions: ClientAction[];
  awaiting_signature: boolean;   // заявитель без права подписи попросил подписанта; подписант видит пометку в списке
  objection: { status: "PENDING" | "RESOLVED"; created_at: string; outcome_text: string | null } | null;
  created_at: string; updated_at: string;
}
export interface ApplicationListItem {
  id: string; number: number; state: ApplicationState; stage: Stage; product_code: ProductCode;
  amount: number; awaiting_signature: boolean; updated_at: string;
}
// GET /applications?company_id= → ApplicationListItem[] (новые первыми, без пагинации — у клиента их единицы)

// ---------- Действия клиента ----------
export interface OtpRequest { purpose: OtpPurpose; party_id?: string }       // POST /applications/{id}/otp
export interface OtpResponse { otp_id: string; demo_code: string; expires_at: string } // код 6 цифр, 5 минут, A5
export interface SubmitRequest {                                             // POST /applications/{id}/submit
  otp_id: string; code: string;
  consents: { pdn: true; bki: true; auto_decision: boolean }; // auto_decision обязателен для IP, для OOO игнорируется
}
export interface InfoResponseRequest {                                      // POST /applications/{id}/info-response
  answers: { item_code: InfoItemCode; value?: number; comment: string }[]; // comment 3–1000 символов
}
export interface AcceptOfferRequest { offer_version: number }               // POST …/offer/accept
export interface SignRequest { otp_id: string; code: string; party_id: string } // POST …/sign
export interface ObjectionRequest { text: string }                          // POST …/objection, 10–2000 символов
// POST …/offer/reject, …/withdraw, …/request-signature — без тела. Все действия возвращают ApplicationClient.
// request-signature: только пользователь без can_sign, только в DRAFT; ставит awaiting_signature=true и событие SIGNATURE_REQUESTED.

// ---------- Андеррайтер и банк ----------
export interface QueueItem { // GET /underwriting/queue → QueueItem[], сортировка по waiting_since
  id: string; number: number; company_name: string; company_kind: CompanyKind; product_code: ProductCode;
  amount: number; grade: Grade | null; route_reason: RouteReason; waiting_since: string;
}
export interface FactorLine { code: string; title: string; value: string; points: number; max_points: number; rule: string }
export interface RuleFired { code: string; title: string; value: string; threshold: string; effect: "STOP" | "ROUTE" | "INFO" | "POLICY" }
export interface PolicyCalc {
  rate: number; avg_turnover: number; existing_payments: number; free_payment: number;
  cap_by_turnover: number; max_amount: number; requested_payment: number | null; ptr_requested: number | null;
  steps: string[]; // человекочитаемый ход расчёта встречного, по шагам decision-model §6
}
export interface DecisionBank {
  id: string; kind: "AUTO" | "MANUAL";
  outcome: "APPROVE" | "COUNTER" | "DECLINE" | "MANUAL" | "REQUEST_INFO" | "RETRY_ENRICHMENT";
  client_reason_code: string | null;
  route_reason: RouteReason | null; grade: Grade | null; score: number | null;
  factors: FactorLine[]; rules_fired: RuleFired[]; internal_reasons: string[];
  policy: PolicyCalc | null;
  recommendation: { outcome: "APPROVE" | "COUNTER" | "DECLINE"; amount: number | null; term_months: number | null; rate: number | null } | null;
  what_if: string[]; // «Одобрение при сумме ≤ 1 450 000 ₽», «Одобрение после погашения просрочки»
  config_version: string; key_rate: number; made_by: string | null; comment: string | null; created_at: string;
}
export interface ExternalCheckBank { source: CheckSource; status: CheckStatus; attempts: number; fetched_at: string | null; response: Record<string, unknown> | null }
export interface EventBank { at: string; event_type: string; from_state: ApplicationState | null; to_state: ApplicationState | null; actor: string; reason_code: string | null; note: string | null }
export interface ApplicationBank extends ApplicationClient { // GET /underwriting/applications/{id}
  company: CompanyProfile;
  risk_flags: { aml_flag: boolean; fraud_flag: boolean };
  turnover_12m: { month: string /* "YYYY-MM" */; amount: number }[];
  decisions: DecisionBank[];       // все, новые первыми
  external_checks: ExternalCheckBank[];
  events: EventBank[];
}
export interface UnderwriterDecisionRequest { // POST /underwriting/{id}/decision
  outcome: UnderwriterOutcome;
  amount?: number; term_months?: number;               // обязательны для APPROVE и COUNTER
  client_reason_category?: ClientReasonCategory;       // обязательно для DECLINE
  info_questions?: string[];                           // 1–5 вопросов, обязательно для REQUEST_INFO
  comment: string;                                     // 5–2000 символов, всегда
}
export interface BankListItem extends Omit<QueueItem, "route_reason" | "waiting_since"> { // GET /bank/applications?state=&page=&size=, новые первыми по updated_at
  route_reason: RouteReason | null;  // причина маршрута к специалисту (последнее AUTO-решение или вход в MANUAL_REVIEW), иначе null
  waiting_since: string | null;      // только для MANUAL_REVIEW, иначе null
  state: ApplicationState; updated_at: string;
}
export interface Page<T> { items: T[]; total: number; page: number; size: number } // size ≤ 100; GET /bank/applications → Page<BankListItem>

// ---------- Служебное (только DEMO_MODE=true) ----------
export interface TimeShiftRequest { application_id: string; days: number } // POST /demo/time-shift, 1–400; сдвигает due_at, offer.expires_at, consent.expires_at назад; только INFO_REQUESTED/OFFER_ISSUED/SIGNING (иначе 409); DEMO_MODE=false или нет заявки → 404
export interface TimeShiftResponse { application_id: string; expired_now: boolean; state: ApplicationState }
