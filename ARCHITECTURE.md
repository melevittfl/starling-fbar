# Architecture

## Purpose

This tool computes the maximum balance held in a Starling Bank account during the previous calendar year, for use in FBAR (FinCEN 114) reporting. FBAR requires disclosing the highest balance in each foreign account at any point during the year, expressed in whole US dollars rounded up.

## Structure

The entire implementation lives in `starling/main.py`. There is no database, no configuration file, and no persistent state beyond the CSV written to disk. All logic is expressed as small, independently testable functions.

## Two types of account balance

Starling exposes balances in two fundamentally different ways, which drives the two-track approach in the code.

### Primary account — CSV feed export

The primary current account supports `GET /api/v2/accounts/{accountUid}/feed-export`, which returns a CSV where every row includes a running `Balance (GBP)` column. Finding the peak balance is trivial: parse the CSV and take the maximum value in that column. The tool downloads this CSV and saves it to disk as a record.

Only the primary account type supports this endpoint. Savings accounts return a 400 error, so the tool fetches the CSV for the primary account only.

### Savings spaces — transaction reconstruction

Starling "Spaces" are virtual savings pots that sit within an account. They are modelled as feed categories (`categoryUid`) rather than separate accounts, and they do not appear in the feed-export CSV. The spaces API (`GET /api/v2/account/{accountUid}/spaces`) returns only the **current** balance of each space — there is no historical balance series.

To find the peak balance during the target year the tool reconstructs it by working backwards from the known current balance:

```
opening_balance = current_balance - net(year_transactions) - net(post_year_transactions)
```

Where `net(transactions)` is the sum of all IN amounts minus all OUT amounts (in pence). This gives the balance the space held on 1 January of the target year.

The tool then replays the year's transactions in chronological order, tracking the running balance and recording the highest point reached. This is `compute_max_balance`.

Two separate transaction fetches are required:

- **Year transactions** — 1 Jan to 31 Dec of the target year, used both for the opening balance calculation and for the replay
- **Post-year transactions** — 1 Jan of the current year to now, used only to adjust the opening balance back correctly

### Why post-year transactions are needed

If money moved into a space after the target year ended, the current balance is higher than it was at year-end. Without subtracting those post-year movements, the reconstructed opening balance would be too high, and the peak during the target year would be overstated.

## Combining the two figures

The overall peak balance reported is:

```
overall_max = csv_max + sum(space_maxes)
```

This adds the primary account's peak to each space's peak. When money moves from the primary account into a space, the primary account CSV balance drops by exactly that amount — so the CSV peak already reflects the lower balance. Adding the space peak back in produces a conservative upper bound that may slightly overestimate the true simultaneous total.

This is intentional: for FBAR purposes, overstating is safe and the arithmetic is straightforward to audit. The alternative — tracking the exact moment-by-moment total across all pots — would require merging transaction streams at millisecond precision, which is not worth the complexity for a compliance tool where a slight overestimate carries no risk.

## Output

The tool prints the exact computed figure and a ceiling-rounded whole-pound figure on separate lines:

```
Max balance across all accounts: £15432.18
Max balance rounded up (for FBAR reporting): £15433
```

FBAR requires the figure in whole US dollars rounded up, so the ceiling is taken here in GBP before the filer applies the Treasury's published exchange rate.

## Rate limiting

The Starling API enforces rate limits on the `transactions-between` endpoint. When a 429 response is received, `fetch_space_transactions` retries up to four times with exponential backoff (1 s, 2 s, 4 s, 8 s). This handles bursts caused by iterating over multiple spaces across multiple accounts.

## API calls made

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v2/accounts` | List all accounts |
| `GET /api/v2/accounts/{uid}/feed-export` | Download primary account CSV |
| `GET /api/v2/account/{uid}/spaces` | List spaces for each account |
| `GET /api/v2/feed/account/{uid}/category/{catUid}/transactions-between` | Fetch space transactions (called twice per space: year and post-year) |

## Testing

Tests use `pytest-httpx` to mock HTTP responses at the transport layer. The `httpx.Client` is passed into every function that makes network calls, which makes it straightforward to inject a mock client in tests without monkeypatching global state.

The `datetime` module is monkeypatched in tests that depend on the current date, keeping date logic deterministic without freezing the system clock.

All amounts are stored and computed in pence (minor units) as integers throughout, converting to GBP float only at the point of output. This avoids floating-point rounding errors during arithmetic.
