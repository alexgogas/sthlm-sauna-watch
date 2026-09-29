# STHLM Sauna watch

Checks sthlmsauna.se (Vinterviken) every ~5 minutes and pushes a phone notification
when a slot you're watching frees up. Tapping the notification opens the booking page.
It **never books** – you do that yourself in two taps.

## Setup (≈5 min, once)

**With Claude:** install the `sthlm-sauna` skill (`SKILL.md` in this repo) and ask Claude
to watch a slot. If you don't have a watcher repo yet, it offers to set everything up
using the `gh` CLI (needs a Claude session that can run commands, e.g. Claude Code).

**By hand:**
1. **Phone notifications:** install the **ntfy** app (iOS / Android). Subscribe to a
   topic with a long random name nobody can guess, e.g. `sauna-` followed by 12+ random characters.
2. **GitHub repo:** click **Use this template** → *Create a new repository*, name it
   `sthlm-sauna-watch` and make it **public** (public = unlimited free Actions minutes).
3. **Secret:** repo → Settings → Secrets and variables → Actions → *New repository secret*:
   `NTFY_TOPIC` = your topic name.
4. **Test:** Actions tab → *Sauna watch* → *Run workflow*. The log should end with "Nothing to check".
5. **Trigger:** set up the 5-minute trigger below.

## Reliable 5-minute trigger (cron-job.org)

GitHub's own schedule is best-effort and in practice runs only every few hours, which
misses most cancellations. A free [cron-job.org](https://cron-job.org) job fixes this by
starting the workflow every 5 minutes through GitHub's API.

1. **GitHub token:** github.com → Settings → Developer settings → Personal access tokens →
   *Fine-grained tokens* → *Generate new token*.
   - Name: `sauna cron`. Expiration: up to a year (set a reminder to renew it).
   - Repository access: *Only select repositories* → `sthlm-sauna-watch`.
   - Permissions → Repository permissions → **Actions: Read and write**. Nothing else.
   - Generate and copy the token. It can only start and read this repo's workflows.
2. **cron-job.org:** sign up (free) → *Create cronjob*:
   - URL: `https://api.github.com/repos/<your username>/sthlm-sauna-watch/actions/workflows/watch.yml/dispatches`
   - Schedule: every 5 minutes. Turn on the notification for failed runs.
   - *Advanced* tab: request method **POST**, request body `{"ref":"main"}`, and headers
     `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`,
     `X-GitHub-Api-Version: 2022-11-28`.
   - Save, then use *Test run*: the response should be **204 No Content**.
3. **Check:** after 10 minutes the Actions tab should show *Sauna watch* runs every
   ~5 minutes. `check_every_minutes` still controls how often a run actually checks.

## Changing what you watch

Edit `watches.yml` (GitHub mobile app or web → pencil icon → commit). Examples are in the file.

- **How often:** set `check_every_minutes` at the top of the file (default 15, minimum 5).
- **Stops after a find:** once a watch alerts, it's no longer checked, so you won't get
  more alerts for it. To re-arm it, edit it in any way (even just the name) or remove and
  re-add it.
- **Stops an hour before:** slots starting within the next hour are ignored, and a watch
  whose last possible slot is under an hour away stops being checked. When no watch is
  left to check, runs exit straight away.

**Privacy option:** in a public repo anyone can read `watches.yml`. To keep your
schedule private, put the same YAML (starting with `watches:`) in a repository
**variable** named `WATCHES` (Settings → Secrets and variables → Actions → Variables); it can include `check_every_minutes` too.
Only you can see it, and it overrides the file.

**Managing watches with Claude:** the `sthlm-sauna` skill can add, list and remove
watches for you. It edits the `WATCHES` variable with the `gh` CLI, so this needs a
Claude session that can run commands on a machine where `gh` is logged in.

## Notes
- GitHub disables workflows in public repos after 60 days with no commits. The
  cron-job.org job then fails (you get its failure email): click "Enable workflow" in
  the Actions tab.
- When the token expires, cron-job.org starts failing too: create a new token and
  paste it into the job's Authorization header.
- Session IDs: 1793 Mixbastu, 1792 Dambastu, 1786 Herrbastu, 25382 Yoga & Sauna,
  78381 Aufguss, 87268 Allmänhetens pass.
