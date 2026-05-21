# Starling FBAR Helper

A command-line tool that fetches the previous calendar year's transaction data from the Starling Bank API, saves a transaction CSV, and reports the highest balance held across all accounts and savings spaces during the year — the figure needed for FBAR (FinCEN 114) foreign bank account reporting.

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
   - `savings-goal:read`
   - `savings-goal-transaction:read`
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
2. Determines the target date range — 1 January to 31 December of the previous calendar year
3. Fetches all accounts via `GET /api/v2/accounts`
4. Downloads the primary account's transaction feed as CSV via `GET /api/v2/accounts/{accountUid}/feed-export` and saves it to disk as `feed_export_{account_name}_{year}.csv`
5. For every account, fetches all active savings spaces via `GET /api/v2/account/{accountUid}/spaces`
6. For each space, fetches transactions during the target year and from 1 January of the current year to now, then reconstructs the peak balance the space held at any point during the target year
7. Reports the combined peak balance and a ceiling-rounded figure ready for FBAR entry

## Expected output

```
Trip Fund (Space, Personal): 2500.0
Rainy Day (Space, Personal): 800.0

Max balance across all accounts: £15432.18
Max balance rounded up (for FBAR reporting): £15433
```

The transaction CSV is written to the project root, e.g. `feed_export_personal_2025.csv`. This file is excluded from git.

## Running tests

```bash
uv run pytest -v
```
