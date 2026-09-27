# STHLM Sauna watch

Checks sthlmsauna.se (Vinterviken) every ~5 minutes and pushes a phone notification
when a slot you're watching frees up. Tapping the notification opens the booking page.
It **never books** – you do that yourself in two taps.

## Setup (≈10 min, once)

1. **Phone notifications:** install the **ntfy** app (iOS / Android). Subscribe to a
   topic with a long random name nobody can guess, e.g. `sauna-` followed by 12+ random characters.
2. **GitHub repo:** create a new **public** repo (public = unlimited free Actions minutes;
   a private repo would run out at a 5-min interval). Upload everything in this folder,
   including the hidden `.github/workflows/watch.yml`.
3. **Secret:** repo → Settings → Secrets and variables → Actions → *New repository secret*:
   `NTFY_TOPIC` = your topic name.
4. **Test:** Actions tab → *Sauna watch* → *Run workflow*. Check the log shows slots.

## Changing what you watch

Edit `watches.yml` (GitHub mobile app or web → pencil icon → commit). Examples are in the file.

- **How often:** set `check_every_minutes` at the top of the file (minimum and default: 5).
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
- GitHub's scheduler may delay runs by several minutes at busy times.
- GitHub pauses scheduled workflows in public repos after 60 days with no commits.
  If that happens, click "Enable workflow" in the Actions tab.
- Session IDs: 1793 Mixbastu, 1792 Dambastu, 1786 Herrbastu, 25382 Yoga & Sauna,
  78381 Aufguss, 87268 Allmänhetens pass.
