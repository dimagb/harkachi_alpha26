"""Explicit client projection with only public decision details."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import member_company
from app.decision import DEFAULT_CONFIG, eligible_date
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    Decision,
    InfoRequest,
    Offer,
    Party,
    ReasonCatalog,
    User,
)
from app.schemas.api import (
    ApplicationClient,
    ApplicationListItem,
    ClientReason,
    InfoRequestClient,
    OfferClient,
    PartyClient,
    Stage,
    TimelineItem,
)

STAGES = (
    ("APPLICATION", "Заявка"),
    ("CHECK", "Проверка данных"),
    ("ASSESSMENT", "Оценка"),
    ("DECISION", "Решение"),
    ("SIGNING", "Подписание"),
    ("DISBURSEMENT", "Выдача"),
)
# index, what_happens, what_to_do, current stage status, ordered candidate actions
STATE_VIEWS = {
    "DRAFT": (
        1,
        "Заявка ещё не отправлена в банк",
        "Проверьте параметры заявки, подпишите согласия и отправьте её",
        "action_required",
        ("EDIT_DRAFT", "SUBMIT", "REQUEST_SIGNATURE", "WITHDRAW"),
    ),
    "SUBMITTED": (
        1,
        "Заявка отправлена, скоро начнём проверку",
        None,
        "current",
        ("WITHDRAW",),
    ),
    "VALIDATION": (2, "Проверяем данные заявки", None, "current", ("WITHDRAW",)),
    "ENRICHMENT": (
        2,
        "Запрашиваем сведения о компании в реестре, бюро кредитных историй и налоговой",
        None,
        "current",
        ("WITHDRAW",),
    ),
    "INFO_REQUESTED": (
        2,
        "Нужно уточнить данные заявки",
        "Ответьте на вопросы банка до указанного срока",
        "action_required",
        ("ANSWER_INFO_REQUEST", "WITHDRAW"),
    ),
    "ASSESSMENT": (3, "Оцениваем заявку", None, "current", ("WITHDRAW",)),
    "MANUAL_REVIEW": (
        3,
        "Заявку рассматривает специалист банка — обычно до 1 рабочего дня",
        None,
        "current",
        ("WITHDRAW",),
    ),
    "OFFER_ISSUED": (
        4,
        "Предложение готово",
        "Примите предложение или откажитесь от него до указанного срока",
        "action_required",
        ("ACCEPT_OFFER", "REJECT_OFFER", "WITHDRAW"),
    ),
    "DECLINED": (
        4,
        "Банк не может одобрить заявку",
        "Посмотрите причину и что можно сделать",
        "failed",
        ("NEW_APPLICATION",),
    ),
    "SIGNING": (
        5,
        "Готовим договор к подписанию",
        "Подпишите договор кодом подтверждения",
        "action_required",
        ("SIGN", "WITHDRAW"),
    ),
    "SIGNED": (5, "Договор подписан, готовим выдачу", None, "current", ()),
    "DISBURSED": (6, "Деньги зачислены на счёт", None, "done", ("NEW_APPLICATION",)),
    "WITHDRAWN": (
        None,
        "Заявка отозвана",
        "Можно подать новую заявку",
        "cancelled",
        ("NEW_APPLICATION",),
    ),
    "EXPIRED": (
        None,
        "Срок заявки истёк",
        "Можно подать новую заявку",
        "cancelled",
        ("NEW_APPLICATION",),
    ),
}


def _presentation(
    session: Session, application: Application, user: User, *, for_bank: bool = False
):
    membership = None
    if not for_bank:
        _, membership = member_company(application.company_id, user, session)
    parties = list(
        session.scalars(
            select(Party)
            .where(Party.application_id == application.id)
            .order_by(Party.created_at, Party.id)
        )
    )
    events = list(
        session.scalars(
            select(ApplicationEvent)
            .where(
                ApplicationEvent.application_id == application.id,
                ApplicationEvent.event_type == "STATE_CHANGED",
            )
            .order_by(ApplicationEvent.created_at, ApplicationEvent.id)
        )
    )
    index, happens, todo, status, candidates = STATE_VIEWS[application.state]
    last = events[-1] if events else None
    if index is None:
        index = STATE_VIEWS[last.from_state][0] if last is not None else 1
    actions = []
    for action in () if for_bank else candidates:
        if (
            action in {"SUBMIT", "ACCEPT_OFFER", "REJECT_OFFER"}
            and not membership.can_sign
        ):
            continue
        if action == "REQUEST_SIGNATURE" and (
            membership.can_sign or application.awaiting_signature
        ):
            continue
        if (
            action == "WITHDRAW"
            and application.state != "DRAFT"
            and not membership.can_sign
        ):
            continue
        if action == "SIGN" and not any(
            party.user_id == user.id and party.status == "PENDING" for party in parties
        ):
            continue
        actions.append(action)
    if (
        not for_bank
        and application.state in {"DRAFT", "OFFER_ISSUED"}
        and not membership.can_sign
    ):
        status, todo = "current", "Ждём решения подписанта компании"
    if application.state == "SIGNING" and "SIGN" not in actions:
        status, todo = "current", "Ждём подписи остальных участников"
    if (
        application.state == "WITHDRAWN"
        and last is not None
        and last.reason_code == "CLIENT_REJECTED_OFFER"
    ):
        happens = "Вы отказались от предложения"
    code, title = STAGES[index - 1]
    stage = Stage(
        index=index, code=code, title=title, what_happens=happens, what_to_do=todo
    )
    first_entry = {}
    for event in events:
        event_index = STATE_VIEWS[event.to_state][0]
        if event_index is not None:
            first_entry.setdefault(event_index, event.created_at.isoformat())
    timeline = []
    for number, (code, title) in enumerate(STAGES, 1):
        item_status = (
            "done" if number < index else status if number == index else "pending"
        )
        at = first_entry.get(number) if number <= index else None
        if item_status == "cancelled" and last is not None:
            at = last.created_at.isoformat()
        timeline.append(
            TimelineItem(stage_code=code, title=title, status=item_status, at=at)
        )
    return stage, timeline, actions, parties


OFFER_EXPLANATIONS = {
    "business_age": "Бизнес работает больше 3 лет",
    "industry_risk": "Отрасль с низким риском",
    "mass_registration": "Руководитель и адрес компании не массовые",
    "turnover_stability": "Стабильные поступления на счёт",
    "turnover_trend": "Поступления на счёт не снижаются",
    "zero_months": "Поступления на счёт каждый месяц",
    "payment_to_turnover": "Низкая долговая нагрузка",
    "debt_to_turnover": "Небольшой долг относительно оборота",
    "delinquency_12m": "Нет просрочек по кредитам",
    "credit_history_length": "Длинная кредитная история",
    "bureau_inquiries_30d": "Мало обращений за кредитами в последний месяц",
    "payment_discipline": "Нет долгов по налогам и судебных взысканий",
}


def _offer_client(
    session: Session, application: Application, decision: Decision | None
) -> OfferClient | None:
    offer = (
        session.get(Offer, application.current_offer_id)
        if application.current_offer_id is not None
        else None
    )
    if offer is None:
        return None
    auto = session.scalar(
        select(Decision)
        .where(Decision.application_id == application.id, Decision.kind == "AUTO")
        .order_by(Decision.created_at.desc(), Decision.id.desc())
        .limit(1)
    )
    explanation = [
        OFFER_EXPLANATIONS[factor["code"]]
        for factor in (auto.factors if auto else [])
        if factor["points"] == factor["max_points"]
        and factor["code"] in OFFER_EXPLANATIONS
    ][:3]
    if not explanation:
        explanation = ["Условия рассчитаны по данным о вашем бизнесе"]
    requested = None
    counter_reason = None
    if offer.kind == "COUNTER":
        requested = {
            "amount": application.amount,
            "term_months": application.term_months,
        }
        counter_reason = (
            "Специалист банка подобрал сумму и срок "
            "с учётом ваших оборотов и обязательств"
            if decision is not None and decision.kind == "MANUAL"
            else "Лимит овердрафта ограничен 40% среднемесячных поступлений на счёт"
            if offer.product_code == "OVERDRAFT"
            else "Платёж по запрошенным условиям был бы слишком большим для текущих "
            "оборотов. Предлагаем условия, при которых платёж не превышает 30% "
            "среднемесячных поступлений на счёт"
        )
    return OfferClient(
        id=str(offer.id),
        version=offer.version,
        kind=offer.kind,
        status=offer.status,
        product_code=offer.product_code,
        amount=offer.amount,
        term_months=offer.term_months,
        rate=offer.rate,
        monthly_payment=offer.monthly_payment,
        expires_at=offer.expires_at.isoformat(),
        explanation=explanation,
        requested=requested,
        counter_reason=counter_reason,
    )


def _client_reason(
    session: Session, application: Application, decision: Decision | None
) -> ClientReason | None:
    if application.state != "DECLINED" or decision is None:
        return None
    reason = session.scalar(
        select(ReasonCatalog).where(
            ReasonCatalog.code == decision.client_reason_code,
            ReasonCatalog.client_visible.is_(True),
        )
    )
    if reason is None:
        return None
    action = reason.client_action
    retry_after = None
    if reason.code == "SF_OVERDUE":
        retry_after = decision.created_at.astimezone(
            ZoneInfo("Europe/Moscow")
        ).date() + timedelta(days=30)
    elif reason.code == "SF_AGE":
        company = session.get(Company, application.company_id)
        retry_after = eligible_date(company.reg_date, DEFAULT_CONFIG)
        if action is not None:
            action = action.replace(
                "{date}", (retry_after - timedelta(days=1)).strftime("%d.%m.%Y")
            )
    return ClientReason(
        code=reason.code,
        category=reason.client_category
        if reason.client_category is not None
        else decision.inputs_snapshot.get("client_category"),
        text=reason.client_text,
        action=action,
        retry_after=retry_after.isoformat() if retry_after else None,
    )


def _info_request_client(
    session: Session, application: Application
) -> InfoRequestClient | None:
    if application.state != "INFO_REQUESTED":
        return None
    request = session.scalar(
        select(InfoRequest)
        .where(
            InfoRequest.application_id == application.id,
            InfoRequest.responded_at.is_(None),
        )
        .order_by(InfoRequest.created_at.desc(), InfoRequest.id.desc())
        .limit(1)
    )
    if request is None:
        return None
    return InfoRequestClient(
        id=str(request.id), items=request.items, due_at=request.due_at.isoformat()
    )


def to_client(
    session: Session, application: Application, user: User, *, for_bank: bool = False
) -> ApplicationClient:
    stage, timeline, actions, parties = _presentation(
        session, application, user, for_bank=for_bank
    )
    decision = session.scalar(
        select(Decision)
        .where(Decision.application_id == application.id)
        .order_by(Decision.created_at.desc(), Decision.id.desc())
        .limit(1)
    )
    # TODO(lead): заполнить objection и OBJECT в B-09.
    return ApplicationClient(
        id=str(application.id),
        number=application.number,
        version=application.version,
        company_id=str(application.company_id),
        state=application.state,
        stage=stage,
        timeline=timeline,
        product_code=application.product_code,
        amount=application.amount,
        term_months=application.term_months,
        purpose=application.purpose,
        purpose_text=application.purpose_text,
        declared_revenue_year=application.declared_revenue_year,
        offer=_offer_client(session, application, decision),
        client_reason=_client_reason(session, application, decision),
        info_request=_info_request_client(session, application),
        objection=None,
        parties=[
            PartyClient(
                id=str(party.id),
                role=party.role,
                full_name=party.full_name,
                signed=party.status == "SIGNED",
                is_me=not for_bank and party.user_id == user.id,
            )
            for party in parties
        ],
        allowed_actions=actions,
        awaiting_signature=application.awaiting_signature,
        created_at=application.created_at.isoformat(),
        updated_at=application.updated_at.isoformat(),
    )


def to_list_item(
    session: Session, application: Application, user: User
) -> ApplicationListItem:
    stage, _, _, _ = _presentation(session, application, user)
    return ApplicationListItem(
        id=str(application.id),
        number=application.number,
        state=application.state,
        stage=stage,
        product_code=application.product_code,
        amount=application.amount,
        awaiting_signature=application.awaiting_signature,
        updated_at=application.updated_at.isoformat(),
    )
