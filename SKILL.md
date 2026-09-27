---
name: "sthlm-sauna"
description: "Check STHLM Sauna (sthlmsauna.se) Vinterviken availability by day, time, session type or group size, and add, list or remove watches (GitHub Actions + phone push) that alert when a full slot frees up. Never books without approval."
---

# STHLM Sauna – availability & slot watcher

The user is a member at STHLM Sauna Vinterviken, Stockholm. All times are Europe/Stockholm.

## HARD RULE: never book without approval
Never book, pay, submit or click any booking/confirm control unless the user has said an explicit "yes, book <that slot>" in the current conversation. Checking availability is read-only and always fine.

## 1. Check availability (read-only, no login needed)
Fetch (WebFetch / web fetch):

```
https://sthlmsauna.se/wp-json/sthlmsauna/v1/availability?product_ids=1786%2C1792%2C1793%2C25382%2C36299%2C50855%2C73394%2C78381%2C87268&from=<FROM>&to=<TO>&persons=<N>&resource_id=1787
```

- `from` / `to`: Unix seconds. `from` = 00:00 Stockholm time on the first day wanted; `to` = 00:00 the day after the last day wanted. Keep the range small (1–7 days) so the response stays short. Compute timestamps carefully (CEST = UTC+2 until the last Sunday of October, then CET = UTC+1). Example: 2026-09-27 00:00 CEST = 1790460000.
- `persons`: 1, 2 or 3 (group size). Availability is per group size.
- `resource_id=1787` = Vinterviken.

The response has `slots[]`, each with `product_id`, `start`, `end` (ISO with offset), `available` (free spots), `booked`.
Use `available` only. Ignore `can_book` / `book_reason`, because anonymous fetches show `not_subscribed` for member sessions even though the user can book them.

### product_id → session
| id | Session |
|---|---|
| 1793 | Mixbastu |
| 1792 | Dambastu |
| 1786 | Herrbastu |
| 25382 | Yoga & Sauna (Mon) |
| 78381 | Aufguss (Fri/Sun mornings) |
| 87268 | Allmänhetens pass (Wed 17–19) |
| 36299, 50855, 73394 | other/unused (keep in the query) |

Slots are 2 hours long. Weekly member schedule: Mon Herrbastu 07–11, Yoga 11–13, Mix 13–01 · Tue Mix 07–17, Dam 17–21, Mix 21–01 · Wed Mix 07–17, Public 17–19, Mix 19–01 · Thu Dam 07–13, Mix 13–01 · Fri Aufguss 07–09, Mix 11–01 · Sat Mix 07–01 · Sun Aufguss 07–09, Mix 09–01.

### Presenting results
Apply the user's filters (days, time window, session type, persons). Show a compact list: `Tue 30 Sep 21:00 · Mixbastu · 3 free`. Say clearly if nothing matches, and mention the nearest alternative. End with the booking link: https://sthlmsauna.se/boka/

## 2. Watches: alert when a full slot frees up
Watches run on GitHub Actions in the user's public `sthlm-sauna-watch` repo. Below, `$REPO` means `"$(gh api user --jq .login)/sthlm-sauna-watch"`. It checks every 5+ minutes and sends a phone push via ntfy that opens the booking page. It never books.
The watch list is private: it lives in the repo **variable** `WATCHES` (a YAML document), not in the repo files. Manage it with the `gh` CLI; always pass `--repo $REPO`.

If this surface can't run shell commands with a logged-in `gh`, say so. Show the user the full YAML to paste at github.com/<their username>/sthlm-sauna-watch → Settings → Secrets and variables → Actions → Variables → `WATCHES`.

### Format
```yaml
check_every_minutes: 5        # how often to check; minimum and default 5
watches:
  - name: Sat 4 Oct 21:00 Mix x2   # shown in the notification; keep it short
    session: Mixbastu              # Mixbastu | Dambastu | Herrbastu | Yoga & Sauna | Aufguss | Allmänhetens pass
    date: 2026-10-04               # one day, YYYY-MM-DD
    time: "21:00"                  # exact slot start (quoted)
    persons: 2                     # 1-3; alert only when this many spots are free (default 1)
```
Other optional fields: `days: [tue, wed]`, `after: "19:00"`, `before: "23:00"` (slot start window), `from_date` / `to_date` (default: today to 14 days ahead), and `alert_if_already_open: false` (alert only on cancellations, not on slots already free when the watch starts).

How the watcher behaves, so you can explain it:
- A watch stops after its first alert. Any edit to a watch (even its name) re-arms it.
- Slots starting within 1 hour are ignored. A watch whose last possible slot is under an hour away stops being checked.
- Only the `WATCHES` variable is used when it's set; `watches.yml` in the repo is ignored.

### Read / write
- Read: `gh variable get WATCHES --repo $REPO`. If it isn't found, start from `check_every_minutes: 5` + `watches: []`.
- Write: always read, modify and write back the **whole** document. Keep `check_every_minutes` and the other watches exactly as they were. Write the YAML to a temp file, then run `gh variable set WATCHES --repo $REPO < <file>`. Read it back to confirm.
- On every write, drop watches whose `date` / `to_date` is in the past, and tell the user which ones you dropped.

### Add a watch
1. Check current availability first (section 1). If the slot is already open, say so with the booking link and ask whether the user still wants a watch.
2. Build the entry. For a specific slot use `session`, `date`, `time` and `persons`. For a filter ("any Mixbastu Tue–Thu after 19"), use `days` / `after` / `before` / dates, plus `alert_if_already_open: false` if the user has just seen the slots that are already open.
3. Write it (see above). Then run `gh workflow view watch.yml --repo $REPO`. If the workflow is disabled (GitHub pauses it after 60 days without commits), enable it with `gh workflow enable`.
4. Confirm in one or two lines: what is watched, for how many people, how often, and that it stops after the alert or an hour before the slot. Remind the user that GitHub can run checks a few minutes late.

### List / remove / change
- List: show one line per watch, e.g. `Sat 4 Oct 21:00 · Mixbastu · x2`, and mark expired ones. Whether a watch has already alerted isn't visible (that state is kept inside the Actions run); the user will have had the notification.
- Remove: write the document back without that watch. To remove all, use `watches: []`.
- Change frequency: set `check_every_minutes` (5 minimum; lower values act as 5).
- Pause or resume everything: `gh workflow disable watch.yml` / `gh workflow enable watch.yml`.

## 3. Booking (only after explicit approval)
- On a phone, the fastest path is for the user to tap https://sthlmsauna.se/boka/, choose the group size, date and slot, and confirm. They're already logged in there.
- If Claude in Chrome tools are available and the user says "yes, book it", open https://sthlmsauna.se/boka/ in a new tab, pick the group size, the date and the slot, then stop at the final confirm button. Show the user exactly what will be booked and get one more "yes" before clicking. Never enter passwords or payment details.