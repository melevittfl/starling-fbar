# Starling FBAR Helper

A command-line tool that fetches the previous calendar year's transaction feed from the Starling Bank API across all accounts (current, savings, spaces), saves a CSV file per account, and reports the highest balance recorded across all accounts combined — the figure needed for FBAR (FinCEN 114) filings.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Create a personal access token

1. Log in to the [Starling Developer Portal](https://developer.starlingbank.com)
2. Go to **Personal** > **Create Token**
3. Grant the following scopes:
   - `account:read`
   - `account-list:read`
   - `account-identifier:read`
   - `feed-export-csv:read`
4. Copy the token

### 3. Save the token

Create a file called `token.txt` in the project root and paste your token into it.
This file is excluded from git via `.gitignore` and will never be committed.

## Running

```bash
uv run starling
```

## How it works

1. Reads the bearer token from `token.txt`
2. Determines the date range — 1 January to 31 December of the previous calendar year
3. Calls `GET /api/v2/accounts` to retrieve all accounts (current, savings, spaces)
4. For each account, calls `GET /api/v2/accounts/{accountUid}/feed-export` to download that year's transactions as CSV
5. Saves each account's CSV to disk as `feed_export_{account_name}_{year}.csv`
6. Combines all transaction rows across every account and finds the single highest `Balance (GBP)` value
7. Prints the overall maximum balance

## Expected output

```
Max balance across all accounts: 12345.67
```

One CSV file per account is written to the project root, e.g. `feed_export_personal_2025.csv` and `feed_export_test_account_2025.csv`. These files are excluded from git.

## Running tests

```bash
uv run pytest -v
```
