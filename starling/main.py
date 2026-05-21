import csv
import io
from datetime import datetime

import httpx

BASE_URL = "https://api.starlingbank.com"


def read_token(path: str) -> str:
    with open(path) as f:
        return f.read().strip()


def get_default_account(client: httpx.Client) -> str:
    response = client.get("/api/v2/accounts")
    response.raise_for_status()
    accounts = response.json()["accounts"]
    return next(a["accountUid"] for a in accounts if a["accountType"] == "PRIMARY")


def get_date_range() -> tuple[str, str]:
    year = datetime.now().year - 1
    return f"{year}-01-01", f"{year}-12-31"


def fetch_feed_export(client: httpx.Client, account_uid: str, start: str, end: str) -> str:
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
    return max(float(row["Balance (GBP)"]) for row in reader)


def main() -> None:
    token = read_token("token.txt")
    start, end = get_date_range()
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        account_uid = get_default_account(client)
        csv_content = fetch_feed_export(client, account_uid, start, end)
    output_path = f"feed_export_{start[:4]}.csv"
    save_csv(csv_content, output_path)
    max_balance = find_max_balance(csv_content)
    print(f"Max balance: {max_balance}")


if __name__ == "__main__":
    main()
