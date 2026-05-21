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


def read_token(path: str) -> str:
    with open(path) as f:
        return f.read().strip()


def get_all_accounts(client: httpx.Client) -> list[Account]:
    response = client.get("/api/v2/accounts")
    response.raise_for_status()
    return [
        Account(uid=a["accountUid"], name=a["name"])
        for a in response.json()["accounts"]
    ]


def get_date_range() -> tuple[str, str]:
    year = datetime.now().year - 1
    return f"{year}-01-01", f"{year}-12-31"


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


def save_csv(content: str, path: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def find_max_balance(csv_content: str) -> float:
    reader = csv.DictReader(io.StringIO(csv_content))
    return max((float(row["Balance (GBP)"]) for row in reader), default=0.0)


def account_filename(name: str, year: str) -> str:
    safe = name.lower().replace(" ", "_")
    return f"feed_export_{safe}_{year}.csv"


def combine_csvs(csv_contents: list[str]) -> str:
    if not csv_contents:
        return ""
    lines = csv_contents[0].splitlines()
    for content in csv_contents[1:]:
        lines.extend(content.splitlines()[1:])  # skip header
    return "\n".join(lines) + "\n"


def main() -> None:
    token = read_token("token.txt")
    start, end = get_date_range()
    year = start[:4]
    csv_contents = []
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        accounts = get_all_accounts(client)
        for account in accounts:
            try:
                csv_content = fetch_feed_export(client, account.uid, start, end)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    print(f"Skipping {account.name}: {e.response.json()}")
                    continue
                raise
            save_csv(csv_content, account_filename(account.name, year))
            csv_contents.append(csv_content)
    overall_max = find_max_balance(combine_csvs(csv_contents))
    print(f"Max balance across all accounts: {overall_max}")


if __name__ == "__main__":
    main()
