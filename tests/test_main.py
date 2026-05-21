import datetime

import httpx
import pytest

from starling.main import (
    Account,
    Space,
    account_filename,
    compute_max_balance,
    fetch_feed_export,
    fetch_space_transactions,
    find_max_balance,
    get_all_accounts,
    get_date_range,
    get_spaces,
    get_timestamp_range,
    net_pence,
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

SPACES_RESPONSE = {
    "savingsGoals": [
        {
            "savingsGoalUid": "space-001-uid",
            "name": "Trip Fund",
            "totalSaved": {"currency": "GBP", "minorUnits": 150000},
            "sortOrder": 0,
            "state": "ACTIVE",
        }
    ],
    "spendingSpaces": [],
}

# Two transactions during the target year: +£500 IN, then -£100 OUT
SPACE_TRANSACTIONS_YEAR = {
    "feedItems": [
        {
            "feedItemUid": "txn-001",
            "categoryUid": "space-001-uid",
            "amount": {"currency": "GBP", "minorUnits": 50000},
            "direction": "IN",
            "transactionTime": "2025-03-01T10:00:00.000Z",
            "status": "SETTLED",
        },
        {
            "feedItemUid": "txn-002",
            "categoryUid": "space-001-uid",
            "amount": {"currency": "GBP", "minorUnits": 10000},
            "direction": "OUT",
            "transactionTime": "2025-06-01T10:00:00.000Z",
            "status": "SETTLED",
        },
    ]
}

# One transaction after the target year: +£200 IN
SPACE_TRANSACTIONS_POST = {
    "feedItems": [
        {
            "feedItemUid": "txn-003",
            "categoryUid": "space-001-uid",
            "amount": {"currency": "GBP", "minorUnits": 20000},
            "direction": "IN",
            "transactionTime": "2026-02-01T10:00:00.000Z",
            "status": "SETTLED",
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
    assert accounts[0] == Account(
        uid="primary-account-uid", name="Personal", account_type="PRIMARY"
    )
    assert accounts[1] == Account(
        uid="savings-account-uid", name="Test Saver", account_type="SAVINGS"
    )
    request = httpx_mock.get_requests()[0]
    assert request.headers["authorization"] == "Bearer my-token"


def test_get_spaces(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.starlingbank.com/api/v2/account/primary-account-uid/spaces",
        json=SPACES_RESPONSE,
    )
    with httpx.Client(
        base_url="https://api.starlingbank.com",
        headers={"Authorization": "Bearer my-token"},
    ) as client:
        spaces = get_spaces(client, "primary-account-uid")
    assert len(spaces) == 1
    assert spaces[0] == Space(
        uid="space-001-uid", name="Trip Fund", balance_pence=150000
    )


def test_get_spaces_for_savings_account(httpx_mock):
    savings_spaces_response = {
        "savingsGoals": [
            {
                "savingsGoalUid": "savings-space-uid",
                "name": "Savings",
                "totalSaved": {"currency": "GBP", "minorUnits": 104},
                "sortOrder": 0,
                "state": "ACTIVE",
            }
        ],
        "spendingSpaces": [],
    }
    httpx_mock.add_response(
        method="GET",
        url="https://api.starlingbank.com/api/v2/account/savings-account-uid/spaces",
        json=savings_spaces_response,
    )
    with httpx.Client(
        base_url="https://api.starlingbank.com",
        headers={"Authorization": "Bearer my-token"},
    ) as client:
        spaces = get_spaces(client, "savings-account-uid")
    assert len(spaces) == 1
    assert spaces[0] == Space(
        uid="savings-space-uid", name="Savings", balance_pence=104
    )


def test_fetch_space_transactions(httpx_mock):
    httpx_mock.add_response(
        json=SPACE_TRANSACTIONS_YEAR,
    )
    with httpx.Client(
        base_url="https://api.starlingbank.com",
        headers={"Authorization": "Bearer my-token"},
    ) as client:
        items = fetch_space_transactions(
            client,
            "primary-account-uid",
            "space-001-uid",
            "2025-01-01T00:00:00.000Z",
            "2025-12-31T23:59:59.999Z",
        )
    assert len(items) == 2
    request = httpx_mock.get_requests()[0]
    assert "transactions-between" in str(request.url)
    assert "minTransactionTimestamp" in str(request.url)


def test_net_pence():
    txns = SPACE_TRANSACTIONS_YEAR["feedItems"]
    # +50000 IN, -10000 OUT → net +40000
    assert net_pence(txns) == 40000


def test_net_pence_empty():
    assert net_pence([]) == 0


def test_compute_max_balance():
    # current_balance = £1500 (150000p)
    # year net = +40000p (+£500 IN, -£100 OUT)
    # post net = +20000p (+£200 IN)
    # B_jan1 = 150000 - 40000 - 20000 = 90000p (£900)
    # Replay: 90000 → 140000 (after +50000) → 130000 (after -10000)
    # Peak = 140000p = £1400.00
    year_txns = SPACE_TRANSACTIONS_YEAR["feedItems"]
    post_txns = SPACE_TRANSACTIONS_POST["feedItems"]
    result = compute_max_balance(150000, year_txns, post_txns)
    assert result == 1400.00


def test_get_timestamp_range(monkeypatch):
    class _FixedDatetime:
        @staticmethod
        def now():
            return datetime.datetime(2026, 5, 21, 9, 30, 0)

    monkeypatch.setattr("starling.main.datetime", _FixedDatetime)
    year_start, year_end, post_start, now_ts = get_timestamp_range()
    assert year_start == "2025-01-01T00:00:00.000Z"
    assert year_end == "2025-12-31T23:59:59.999Z"
    assert post_start == "2026-01-01T00:00:00.000Z"
    assert now_ts == "2026-05-21T09:30:00.000Z"


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


def test_overall_max_adds_csv_and_space_peaks():
    import math

    # csv_max = 1001.00, space_maxes = [400.00, 200.00]
    # overall = ceil(1601.00) = 1601 (intentional over-estimate for FBAR)
    csv_max = 1001.00
    space_maxes = [400.00, 200.00]
    overall_max = math.ceil(csv_max + sum(space_maxes))
    assert overall_max == 1601


def test_overall_max_rounds_up():
    import math

    # Fractional pence should round up, never down
    csv_max = 1001.01
    space_maxes = [0.50]
    overall_max = math.ceil(csv_max + sum(space_maxes))
    assert overall_max == 1002


def test_overall_max_no_spaces():
    import math

    csv_max = 1001.00
    space_maxes = []
    overall_max = math.ceil(csv_max + sum(space_maxes))
    assert overall_max == 1001


def test_get_date_range(monkeypatch):
    class _FixedDatetime:
        @staticmethod
        def now():
            return datetime.datetime(2026, 5, 21)

    monkeypatch.setattr("starling.main.datetime", _FixedDatetime)
    start, end = get_date_range()
    assert start == "2025-01-01"
    assert end == "2025-12-31"
