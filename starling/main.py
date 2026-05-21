import csv
import io
from datetime import datetime

import httpx

BASE_URL = "https://api.starlingbank.com"


def read_token(path: str) -> str:
    with open(path) as f:
        return f.read().strip()


def get_default_account(token: str) -> str:
    response = httpx.get(
        f"{BASE_URL}/api/v2/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    accounts = response.json()["accounts"]
    return next(a["accountUid"] for a in accounts if a["accountType"] == "PRIMARY")


def get_date_range() -> tuple[str, str]:
    year = datetime.now().year - 1
    return f"{year}-01-01", f"{year}-12-31"


def fetch_feed_export(token: str, account_uid: str, start: str, end: str) -> str:
    response = httpx.get(
        f"{BASE_URL}/api/v2/accounts/{account_uid}/feed-export",
        params={"start": start, "end": end},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/csv",
        },
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
    account_uid = get_default_account(token)
    start, end = get_date_range()
    csv_content = fetch_feed_export(token, account_uid, start, end)
    year = datetime.now().year - 1
    output_path = f"feed_export_{year}.csv"
    save_csv(csv_content, output_path)
    max_balance = find_max_balance(csv_content)
    print(f"Max balance: {max_balance}")


if __name__ == "__main__":
    main()
