import csv
import io
from dataclasses import dataclass
from datetime import datetime

import httpx

BASE_URL = "https://api.starlingbank.com"


@dataclass
class Account:
    uid: str
    name: str
    account_type: str


@dataclass
class Space:
    uid: str
    name: str
    balance_pence: int


def read_token(path: str) -> str:
    with open(path) as f:
        return f.read().strip()


def get_all_accounts(client: httpx.Client) -> list[Account]:
    response = client.get("/api/v2/accounts")
    response.raise_for_status()
    return [
        Account(uid=a["accountUid"], name=a["name"], account_type=a["accountType"])
        for a in response.json()["accounts"]
    ]


def get_spaces(client: httpx.Client, account_uid: str) -> list[Space]:
    response = client.get(f"/api/v2/account/{account_uid}/spaces")
    response.raise_for_status()
    data = response.json()
    spaces = []
    for goal in data.get("savingsGoals", []):
        if goal.get("state") == "ACTIVE":
            spaces.append(
                Space(
                    uid=goal["savingsGoalUid"],
                    name=goal["name"],
                    balance_pence=goal["totalSaved"]["minorUnits"],
                )
            )
    return spaces


def get_date_range() -> tuple[str, str]:
    year = datetime.now().year - 1
    return f"{year}-01-01", f"{year}-12-31"


def get_timestamp_range() -> tuple[str, str, str, str]:
    now = datetime.now()
    prev_year = now.year - 1
    year_start = f"{prev_year}-01-01T00:00:00.000Z"
    year_end = f"{prev_year}-12-31T23:59:59.999Z"
    post_year_start = f"{now.year}-01-01T00:00:00.000Z"
    now_ts = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return year_start, year_end, post_year_start, now_ts


def fetch_feed_export(
    client: httpx.Client, account_uid: str, start: str, end: str
) -> str:
    response = client.get(
        f"/api/v2/accounts/{account_uid}/feed-export",
        params={"start": start, "end": end},
        headers={"Accept": "text/csv"},
    )
    response.raise_for_status()
    return response.text


def fetch_space_transactions(
    client: httpx.Client,
    account_uid: str,
    category_uid: str,
    min_timestamp: str,
    max_timestamp: str,
) -> list[dict]:
    response = client.get(
        f"/api/v2/feed/account/{account_uid}/category/{category_uid}/transactions-between",
        params={
            "minTransactionTimestamp": min_timestamp,
            "maxTransactionTimestamp": max_timestamp,
        },
    )
    response.raise_for_status()
    return response.json().get("feedItems", [])


def save_csv(content: str, path: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def find_max_balance(csv_content: str) -> float:
    reader = csv.DictReader(io.StringIO(csv_content))
    return max((float(row["Balance (GBP)"]) for row in reader), default=0.0)


def account_filename(name: str, year: str) -> str:
    safe = name.lower().replace(" ", "_")
    return f"feed_export_{safe}_{year}.csv"


def net_pence(transactions: list[dict]) -> int:
    total = 0
    for txn in transactions:
        if txn["direction"] == "IN":
            total += txn["amount"]["minorUnits"]
        else:
            total -= txn["amount"]["minorUnits"]
    return total


def compute_max_balance(
    current_balance_pence: int,
    year_txns: list[dict],
    post_year_txns: list[dict],
) -> float:
    opening = current_balance_pence - net_pence(year_txns) - net_pence(post_year_txns)
    running = opening
    peak = opening
    for txn in sorted(year_txns, key=lambda t: t["transactionTime"]):
        if txn["direction"] == "IN":
            running += txn["amount"]["minorUnits"]
        else:
            running -= txn["amount"]["minorUnits"]
        peak = max(peak, running)
    return peak / 100


def main() -> None:
    token = read_token("token.txt")
    start, end = get_date_range()
    year_start, year_end, post_start, now_ts = get_timestamp_range()
    year = start[:4]
    space_maxes = []

    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        accounts = get_all_accounts(client)
        primary = next(a for a in accounts if a.account_type == "PRIMARY")
        csv_content = fetch_feed_export(client, primary.uid, start, end)
        save_csv(csv_content, account_filename(primary.name, year))

        for account in accounts:
            for space in get_spaces(client, account.uid):
                year_txns = fetch_space_transactions(
                    client, account.uid, space.uid, year_start, year_end
                )
                post_txns = fetch_space_transactions(
                    client, account.uid, space.uid, post_start, now_ts
                )
                space_max = compute_max_balance(
                    space.balance_pence, year_txns, post_txns
                )
                print(f"{space.name} (Space, {account.name}): {space_max}")
                space_maxes.append(space_max)

    csv_max = find_max_balance(csv_content)
    overall_max = csv_max + sum(space_maxes)
    print(f"\nMax balance across all accounts: {overall_max}")


if __name__ == "__main__":
    main()
