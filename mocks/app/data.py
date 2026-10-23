import json
import random
from dataclasses import dataclass
from pathlib import Path

from app.schemas import BkiFullResponse, FnsResponse, RegistryResponse


def checksum(digits: str, weights: tuple[int, ...]) -> str:
    return str(sum(int(d) * w for d, w in zip(digits, weights, strict=True)) % 11 % 10)


def valid_inn(inn: str) -> bool:
    if len(inn) not in (10, 12):
        return False
    if not inn.isascii() or not inn.isdigit() or not int(inn):
        return False
    if len(inn) == 10:
        return inn[-1] == checksum(inn[:9], (2, 4, 10, 3, 5, 9, 4, 6, 8))
    if len(inn) == 12:
        return inn[-2] == checksum(inn[:10], (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)) and (
            inn[-1] == checksum(inn[:11], (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
        )
    return False


def director_inn(inn: str) -> str:
    if len(inn) == 12:
        return inn
    rng = random.Random(int(inn))
    digits = str(rng.randint(1, 9)) + "".join(str(rng.randrange(10)) for _ in range(9))
    digits += checksum(digits, (7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
    return digits + checksum(digits, (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))


@dataclass(frozen=True)
class Company:
    registry: RegistryResponse
    bki: BkiFullResponse
    fns: FnsResponse


def load_companies(root: Path) -> dict[str, Company]:
    personas = json.loads(
        (root / "contracts/personas.json").read_text(encoding="utf-8")
    )
    records = personas["personas"]
    background = root / "data/background.json"
    if background.exists():
        records = (
            records + json.loads(background.read_text(encoding="utf-8"))["companies"]
        )
    companies = {}
    fields = (
        "inn",
        "ogrn",
        "kind",
        "name",
        "status",
        "reg_date",
        "okved_main",
        "address",
        "founders",
    )
    for record in records:
        inn = record["inn"]
        if not valid_inn(inn):
            raise ValueError(f"Некорректный ИНН в данных: {inn}")
        registry = RegistryResponse(
            **{key: record[key] for key in fields},
            director={**record["director"], "inn": director_inn(inn)},
        )
        companies[inn] = Company(
            registry=registry,
            bki=BkiFullResponse(inn=inn, **record["bki"]),
            fns=FnsResponse(inn=inn, **record["fns"]),
        )
    return companies


def generate_company(inn: str) -> Company:
    rng = random.Random(int(inn))
    kind = "OOO" if len(inn) == 10 else "IP"
    ogrn_base = ("1" if kind == "OOO" else "3") + "".join(
        str(rng.randrange(10)) for _ in range(11 if kind == "OOO" else 13)
    )
    ogrn = ogrn_base + str(int(ogrn_base) % (11 if kind == "OOO" else 13) % 10)
    full_name = "Иванов Иван Иванович"
    balance = rng.randint(10, 30) * 100_000
    payment = rng.randint(3, 10) * 10_000
    return Company(
        registry=RegistryResponse(
            inn=inn,
            ogrn=ogrn,
            kind=kind,
            name=f"ООО «Компания {inn}»" if kind == "OOO" else f"ИП {full_name}",
            status="ACTIVE",
            reg_date="2022-01-10",
            okved_main="46.90",
            address="г. Москва, ул. Садовая, д. 10",
            director={"full_name": full_name, "inn": director_inn(inn)},
            founders=[{"full_name": full_name, "share_pct": 100}]
            if kind == "OOO"
            else [],
        ),
        bki=BkiFullResponse(
            inn=inn,
            loans=[
                {
                    "type": "CREDIT",
                    "balance": balance,
                    "monthly_payment": payment,
                    "current_overdue": 0,
                    "max_dpd_12m": 0,
                }
            ],
            summary={
                "monthly_payments_total": payment,
                "total_balance": balance,
                "current_overdue_total": 0,
                "max_dpd_12m": 0,
                "credit_history_months": rng.randint(24, 60),
                "inquiries_30d": 1,
            },
        ),
        fns=FnsResponse(
            inn=inn,
            tax_debt=0,
            enforcement_sum=0,
            arbitration_defendant_sum=0,
            bankruptcy=False,
            msp_registry={"included": True, "category": "MICRO"},
            mass_director=False,
            mass_address=False,
        ),
    )
