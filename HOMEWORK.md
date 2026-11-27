# FairwAI Fellowship
## Take-home exercise: Automation & Data Engineer

**Deadline:** Wednesday, December 2, 2026 at 11:59 PM US Eastern Time
**Expected effort:** about 90 minutes
**Candidate ID:** E34352

The files in this folder were generated for you alone. Please do not share them or post them publicly.

---

### The situation

You have just joined a small pet-transport company. Marketing has exported its leads into `leads_raw.csv`. Sales needs a clean, enriched list and a single revenue figure by tomorrow morning. Nobody is available to answer questions, so make sensible decisions and write them down.

### What is in this folder

| File | What it is |
|---|---|
| `leads_raw.csv` | The raw export |
| `DATA_DICT.md` | Notes from the marketing team on the export |
| `server.py` | Our enrichment service. Start it with `python3 server.py` and open `http://127.0.0.1:8080/` for its documentation. Credits are limited and do not refill. |

### The task

1. **Build `pipeline.py`.** It reads `leads_raw.csv`, writes `leads_clean.csv`, and enriches each valid lead from the service. Running it a second time must not spend credits again.

2. **Produce `leads_clean.csv`** with these columns, in this order:

   `id, name, email, phone, city, state, pet, pet_count, move_date, source, miles, company_type, risk_score, last_seen, flag`

   - `name` as "First Last"
   - `email` in lowercase
   - `phone` in E.164 format
   - `state` as a two-letter code
   - dates as YYYY-MM-DD
   - `miles` in miles
   - `pet_count` as the number of animals
   - `flag` as a short reason for anything you do not fully trust (leave it blank otherwise)

3. **Decide what counts.** A lead is valid if it is not junk, has a usable email address and has a move date on or after 2026-11-01. Merge rows that are the same person into one. Do not merge different people.

4. **Produce `removed.csv`.** It lists every row you removed or merged, the row that survived (if any) and the reason.

5. **Give Sales one number.** This is the expected revenue from valid, de-duplicated leads whose `company_type` is `individual`. Revenue per lead = miles × $1.10 × pet_count.

### What to send back

- `pipeline.py`, `leads_clean.csv`, `removed.csv`
- `api_log.jsonl` (the service writes this file as you use it)
- `NOTES.md`, which must start with these two lines:

  ```
  UNIQUE_VALID_LEADS: <number>
  EXPECTED_REVENUE_USD: <amount to the cent>
  ```

  After that, write about half a page covering: what was wrong with the data, what you decided and why, what you are unsure of, anything you did not finish, and which tools you used and for what.
- Evidence of how you worked: either a git repository with several commits made along the way, or a screen recording of about three minutes.

Put everything in one folder and reply to our email with a zip file attached, or with a link to a GitHub repository or a shared Drive or Dropbox folder that anyone with the link can open.

### How we will look at it

- You may use any tools, including AI assistants. Tell us what you used. We expect you to use them on the job. We care about whether you checked what they gave you.
- If we move forward, you will walk us through your code on a call. We will also change one requirement during the call and ask you to adapt your code while we watch.
- An honest, partial submission is better than a complete one that hides problems.

Good luck. We look forward to seeing your work.
