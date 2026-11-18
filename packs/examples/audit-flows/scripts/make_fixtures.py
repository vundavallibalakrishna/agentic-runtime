"""Write the sample tables for the audit flows. A fixed seed, so the right answers are known.

Everything here is invented. Run it again to rebuild the two CSV files and ``answers.json``.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "fixtures"
SEED = 20261118
QUARTER = (date(2026, 7, 1), date(2026, 9, 30))
BRANCHES = ("North", "South", "East", "West")
SEGMENTS = ("retail", "small-business", "corporate")
CHANNELS = ("branch", "online", "mobile", "transfer")


def main() -> None:
    rng = random.Random(SEED)  # noqa: S311 - sample rows, not a secret
    accounts: list[dict[str, object]] = []
    for number in range(1, 61):
        opened = date(2026, 1, 5) + timedelta(days=rng.randrange(0, 265))
        accounts.append(
            {
                "account_id": f"AC-{number:04d}",
                "opened_on": opened.isoformat(),
                "branch": rng.choice(BRANCHES),
                "segment": rng.choice(SEGMENTS),
                "profile_obtained": "N" if rng.random() < 0.15 else "Y",
                "declared_monthly_amount": rng.choice((5000, 10000, 25000, 50000, 100000)),
            }
        )
    transactions: list[dict[str, object]] = []
    number = 0
    for account in accounts:
        declared = int(str(account["declared_monthly_amount"]))
        # About one account in five moves far more than it declared.
        factor = rng.uniform(1.6, 2.6) if rng.random() < 0.2 else rng.uniform(0.3, 1.2)
        for month in (7, 8, 9):
            remaining = declared * factor
            for _ in range(rng.randrange(3, 7)):
                number += 1
                amount = round(remaining * rng.uniform(0.1, 0.4), 2)
                remaining -= amount
                transactions.append(
                    {
                        "txn_id": f"TX-{number:05d}",
                        "account_id": account["account_id"],
                        "posted_on": date(2026, month, rng.randrange(1, 28)).isoformat(),
                        "amount": amount,
                        "channel": rng.choice(CHANNELS),
                        "user_id": f"U{rng.randrange(1, 13):02d}",
                        "compliance_flag": "Y" if rng.random() < 0.04 else "N",
                    }
                )
    _write("sample-accounts.csv", accounts)
    _write("sample-transactions.csv", transactions)
    (OUT / "answers.json").write_text(json.dumps(_answers(accounts, transactions), indent=2) + "\n")


def _write(name: str, rows: list[dict[str, object]]) -> None:
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _answers(
    accounts: list[dict[str, object]], transactions: list[dict[str, object]]
) -> dict[str, object]:
    """What a correct test finds, worked out here without a model."""
    monthly: dict[tuple[str, str], float] = {}
    for row in transactions:
        key = (str(row["account_id"]), str(row["posted_on"])[:7])
        monthly[key] = monthly.get(key, 0.0) + float(str(row["amount"]))
    recent = [
        row
        for row in accounts
        if QUARTER[0].isoformat() <= str(row["opened_on"]) <= QUARTER[1].isoformat()
    ]
    no_profile = sorted(str(row["account_id"]) for row in recent if row["profile_obtained"] == "N")
    over = sorted(
        str(row["account_id"])
        for row in recent
        if any(
            total > 1.5 * float(str(row["declared_monthly_amount"]))
            for (account, _month), total in monthly.items()
            if account == row["account_id"]
        )
    )
    amounts = [float(str(row["amount"])) for row in transactions]
    return {
        "accounts": len(accounts),
        "transactions": len(transactions),
        "transaction_total": round(sum(amounts), 2),
        "flagged_transactions": sum(1 for row in transactions if row["compliance_flag"] == "Y"),
        "transactions_over_20000": sum(1 for amount in amounts if amount > 20000),
        "opened_in_quarter": len(recent),
        "opened_in_quarter_without_profile": no_profile,
        "opened_in_quarter_over_profile_by_half": over,
        "rule_result": sorted(set(no_profile) | set(over)),
        "by_channel": {
            channel: sum(1 for row in transactions if row["channel"] == channel)
            for channel in CHANNELS
        },
    }


if __name__ == "__main__":
    main()
