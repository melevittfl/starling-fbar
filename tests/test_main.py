import datetime

import httpx
import pytest

from starling.main import (
    Account,
    account_filename,
    combine_csvs,
    fetch_feed_export,
    find_max_balance,
    get_all_accounts,
    get_date_range,
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

CSV_HEADER = (
    "Date,Counter Party,Reference,Type,"
    "Amount (GBP),Balance (GBP),Spending Category,Notes\n"
)

SAMPLE_CSV = (
    CSV_HEADER
    + "01/01/2025,Test Bank,Interest Earned,DEPOSIT INTEREST,1.00,1001.00,INCOME,\n"
    + "04/01/2025,Alice Testuser,1111111111,FASTER PAYMENT,-100.00,901.00,SAVING,\n"
    + "07/01/2025,Example Cards,1234000056780000,DIRECT DEBIT,-50.00,851.00,PAYMENTS,\n"
)

SAVINGS_CSV = (
    CSV_HEADER
    + "15/03/2025,Test Bank,Monthly Transfer,FASTER PAYMENT,500.00,1500.00,SAVING,\n"
    + "30/06/2025,Test Bank,Monthly Transfer,FASTER PAYMENT,500.00,2000.00,SAVING,\n"
)


def test_read_token(tmp_path):
    token_file = tmp_path / "token.txt"
    token_file.write_text("  my-secret-token\n  ")
    assert read_token(str(token_file)) == "my-secret-token"


def test_get_all_accounts(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.starlingbank.com/api/v2/accounts",
        json=ACCOUNTS_RESPONSE,
    )
    with httpx.Client(
        base_url="https://api.starlingbank.com",
        headers={"Authorization": "Bearer my-token"},
    ) as client:
        accounts = get_all_accounts(client)
    assert len(accounts) == 2
    assert accounts[0] == Account(uid="primary-account-uid", name="Personal")
    assert accounts[1] == Account(uid="savings-account-uid", name="Test Saver")
    request = httpx_mock.get_requests()[0]
    assert request.headers["authorization"] == "Bearer my-token"


def test_account_filename():
    assert account_filename("Personal", "2025") == "feed_export_personal_2025.csv"
    assert account_filename("Test Saver", "2025") == "feed_export_test_saver_2025.csv"


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


def test_fetch_feed_export_unsupported_account_type(httpx_mock):
    httpx_mock.add_response(
        status_code=400,
        json=["INVALID_ACCOUNT_TYPE_FOR_ACCOUNT_FEED_EXPORT"],
    )
    with httpx.Client(
        base_url="https://api.starlingbank.com",
        headers={"Authorization": "Bearer my-token"},
    ) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            fetch_feed_export(client, "savings-account-uid", "2025-01-01", "2025-12-31")
    assert exc_info.value.response.status_code == 400


def test_save_csv(tmp_path):
    output_path = tmp_path / "output.csv"
    save_csv(SAMPLE_CSV, str(output_path))
    assert output_path.exists()
    assert output_path.read_text() == SAMPLE_CSV


def test_find_max_balance():
    assert find_max_balance(SAMPLE_CSV) == 1001.00


def test_find_max_balance_empty():
    assert find_max_balance(CSV_HEADER) == 0.0


def test_combine_csvs():
    combined = combine_csvs([SAMPLE_CSV, SAVINGS_CSV])
    lines = combined.strip().splitlines()
    # One header + 3 rows from SAMPLE_CSV + 2 rows from SAVINGS_CSV
    assert len(lines) == 6
    assert lines[0].startswith("Date,")
    assert lines.count(lines[0]) == 1  # header appears exactly once


def test_find_max_balance_combined():
    # SAVINGS_CSV has a higher peak (2000.00) than SAMPLE_CSV (1001.00)
    combined = combine_csvs([SAMPLE_CSV, SAVINGS_CSV])
    assert find_max_balance(combined) == 2000.00


def test_get_date_range(monkeypatch):
    class _FixedDatetime:
        @staticmethod
        def now():
            return datetime.datetime(2026, 5, 21)

    monkeypatch.setattr("starling.main.datetime", _FixedDatetime)
    start, end = get_date_range()
    assert start == "2025-01-01"
    assert end == "2025-12-31"
