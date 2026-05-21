# Starling FBAR Helper

A command-line tool that fetches the previous calendar year's transaction feed from the Starling Bank API, saves it as a CSV file, and reports the highest account balance recorded across all transactions — the figure needed for FBAR (FinCEN 114) filings.

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

Create a file called `token.txt` in the project root and paste your token into it:

```
paste-your-token-here
```

This file is excluded from git via `.gitignore` and will never be committed.

## Running

```bash
uv run starling
```

## How it works

1. Reads the bearer token from `token.txt`
2. Determines the date range — 1 January to 31 December of the previous calendar year
3. Calls `GET /api/v2/accounts` to find the primary account
4. Calls `GET /api/v2/accounts/{accountUid}/feed-export` to download all transactions for that year as CSV
5. Saves the CSV to disk as `feed_export_{year}.csv`
6. Scans the `Balance (GBP)` column across every transaction and prints the maximum balance

## Expected output

```
Max balance: 12345.67
```

A CSV file named `feed_export_2025.csv` (or whichever the previous year is) is also written to the project root. This file is excluded from git.

## Running tests

```bash
uv run pytest -v
```
