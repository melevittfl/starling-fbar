import datetime

import httpx

from starling.main import (
    fetch_feed_export,
    find_max_balance,
    get_date_range,
    get_default_account,
    read_token,
    save_csv,
)

ACCOUNTS_RESPONSE = {
    "accounts": [
        {
            "accountUid": "primary-account-uid",
            "accountType": "PRIMARY",
            "defaultCategory": "00000000-0000-0000-0000-000000000001",
            "currency": "GBP",
            "createdAt": "2020-01-01T00:00:00.000Z",
            "name": "Personal",
        },
        {
            "accountUid": "savings-account-uid",
            "accountType": "SAVINGS",
            "defaultCategory": "00000000-0000-0000-0000-000000000002",
            "currency": "GBP",
            "createdAt": "2020-06-01T00:00:00.000Z",
            "name": "Test Saver",
        },
    ]
}

SAMPLE_CSV = (
    "Date,Counter Party,Reference,Type,Amount (GBP),Balance (GBP),Spending Category,Notes\n"
    "01/01/2025,Test Bank,Interest Earned,DEPOSIT INTEREST,1.00,1001.00,INCOME,\n"
    "04/01/2025,Alice Testuser,1111111111,FASTER PAYMENT,-100.00,901.00,SAVING,\n"
    "07/01/2025,Example Cards,1234000056780000,DIRECT DEBIT,-50.00,851.00,PAYMENTS,\n"
)


def test_read_token(tmp_path):
    token_file = tmp_path / "token.txt"
    token_file.write_text("  my-secret-token\n  ")
    assert read_token(str(token_file)) == "my-secret-token"


def test_get_default_account(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.starlingbank.com/api/v2/accounts",
        json=ACCOUNTS_RESPONSE,
    )
    with httpx.Client(
        base_url="https://api.starlingbank.com",
        headers={"Authorization": "Bearer my-token"},
    ) as client:
        result = get_default_account(client)
    assert result == "primary-account-uid"
    request = httpx_mock.get_requests()[0]
    assert request.headers["authorization"] == "Bearer my-token"


def test_fetch_feed_export(httpx_mock):
    account_uid = "primary-account-uid"
    start = "2025-01-01"
    end = "2025-12-31"
    httpx_mock.add_response(
        text=SAMPLE_CSV,
        headers={"content-type": "text/csv"},
    )
    with httpx.Client(
        base_url="https://api.starlingbank.com",
        headers={"Authorization": "Bearer my-token"},
    ) as client:
        result = fetch_feed_export(client, account_uid, start, end)
    assert result == SAMPLE_CSV
    request = httpx_mock.get_requests()[0]
    assert request.headers["accept"] == "text/csv"
    assert request.headers["authorization"] == "Bearer my-token"
    assert str(request.url).startswith(
        f"https://api.starlingbank.com/api/v2/accounts/{account_uid}/feed-export"
    )


def test_save_csv(tmp_path):
    output_path = tmp_path / "output.csv"
    save_csv(SAMPLE_CSV, str(output_path))
    assert output_path.exists()
    assert output_path.read_text() == SAMPLE_CSV


def test_find_max_balance():
    assert find_max_balance(SAMPLE_CSV) == 1001.00


def test_get_date_range(monkeypatch):
    class _FixedDatetime:
        @staticmethod
        def now():
            return datetime.datetime(2026, 5, 21)

    monkeypatch.setattr("starling.main.datetime", _FixedDatetime)
    start, end = get_date_range()
    assert start == "2025-01-01"
    assert end == "2025-12-31"
