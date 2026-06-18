# whatiride-bot

A Discord bot that asks members what they ride, fuzzy-matches their answer
against a motorcycle dataset, and saves it to a **virtual garage** — including
photos — so the whole server can see and show off their bikes.

No local database files: everything (bike info *and* photos) is stored in a
private Discord channel the bot manages. That means no per-server role limits
and nothing to back up on your machine.

## Commands

| Command | What it does |
|---|---|
| `/whatiride` | Opens a popup form (make / model / badge / year), fuzzy-matches it, and lets you confirm the closest match to add it to your garage. |
| `/garage show [user]` | Shows a rider's bikes as embeds, with photos. Defaults to you. |
| `/garage photo` | Attach or replace a photo for one of your bikes (pick the bike, upload an image). |
| `/garage remove` | Remove one of your bikes. |
| `/whorides <query>` | Lists everyone who rides a given make or model. |
| `/roster` | Summary: total bikes, total riders, and counts per make. |

Riders can have **multiple bikes**. Match results and confirmations are
ephemeral (only the caller sees them); `/garage show`, `/whorides` and
`/roster` post publicly so the server can enjoy them.

## How storage works

The bot keeps one **private archive channel** (auto-created as `garage-archive`,
or set `GARAGE_CHANNEL_ID` to your own). Each bike is one message in it:

- message content: a compact JSON payload (the machine-readable record)
- an embed: human-readable summary
- an optional image attachment: the bike photo (hosted on Discord's CDN)

On startup the bot reads the channel into memory. Writes update both Discord and
the cache. Photo URLs are re-fetched live when shown, so Discord's expiring
attachment links are never stored stale.

> Modals can't accept file uploads, so photos are added via `/garage photo`
> (a slash command with an attachment option), not the `/whatiride` form.

> Scale note: queries scan the in-memory cache rather than a real database.
> This is instant for dozens-to-hundreds of riders; it isn't meant for tens of
> thousands.

## Project layout

```
whatiride-bot/
├── bot.py                  # client, /whatiride modal, /garage, /whorides, /roster
├── requirements.txt
├── .env.example            # copy to .env and fill in
├── data/
│   ├── import_kaggle.py     # builds data/imported.csv from Kaggle bikez (~38k)
│   ├── build_supplement.py  # builds data/supplement.csv (niche bikes base misses)
│   ├── imported.csv         # comprehensive base dataset (committed)
│   └── supplement.csv       # small curated niche dataset (committed)
├── src/
│   ├── dataset.py          # CSV loader -> unique model records w/ year ranges
│   ├── matcher.py          # fuzzy matching + scoring
│   └── store.py            # archive-channel datastore (no local files)
└── tests/
    ├── test_matcher.py
    └── test_store.py
```

## Setup

```bash
cd whatiride-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# the dataset (data/imported.csv + data/supplement.csv) ships in the repo;
# no need to rebuild it to run the bot.

cp .env.example .env
# edit .env: set DISCORD_TOKEN and GUILD_ID
python bot.py
```

## Discord configuration

In the [Discord Developer Portal](https://discord.com/developers/applications):

1. Create an application, add a **Bot**, copy its **token** into `.env`.
2. Invite the bot with the `bot` and `applications.commands` scopes and these
   permissions:
   - **Manage Channels** — only needed once, so the bot can auto-create the
     private archive channel. (Skip it if you create the channel yourself and
     set `GARAGE_CHANNEL_ID`.)
   - **Send Messages**, **Embed Links**, **Attach Files**, **Read Message
     History** — in the archive channel.
   - **Manage Roles** — only if you set `ENABLE_MAKE_ROLE=true`.
3. Set `GUILD_ID` in `.env` so slash-command changes appear instantly.

## Optional: make-level roles

By default the bot only uses the garage store. If you also want a quick visual
badge in the member list, set `ENABLE_MAKE_ROLE=true` to additionally give each
rider a role for their bike's manufacturer (e.g. `Honda`). This stays well under
Discord's 250-role cap because it's one role per brand, not per model. The bot's
role must sit **above** any role it assigns (Server Settings > Roles).

## The dataset

Two committed CSVs are merged at load (`src/dataset.py`):

- **`data/imported.csv`** — the comprehensive base: ~38k models / 570+ makes
  from the Kaggle "all_bikez_curated" dataset (the bikez.com catalog), carrying
  specs (power, engine, cooling, gearbox, transmission, dry weight, seat height,
  fuel capacity, wheelbase). Collapses to ~18k unique model records.
- **`data/supplement.csv`** — a small curated set of niche bikes the base
  misses (e.g. Kraemer, Stark Future, Sur-Ron, Talaria, extra Ohvale variants).

Both ship in the repo, so the deployed bot needs **no** Kaggle/API access.

To refresh or grow the data (dev machine only):

- **Rebuild the base from Kaggle:** put your Kaggle credentials in
  `~/.kaggle/kaggle.json` (username + key), then `python data/import_kaggle.py`.
- **Add niche bikes:** edit the `SPEC` in `data/build_supplement.py` (only add
  what the base genuinely lacks — verify against `imported.csv`), then
  `python data/build_supplement.py`.
- API Ninjas can enrich *specific* models (`?make=&model=`) but its free tier
  can't paginate, so it isn't used for the bulk import.

## Tests

```bash
python -m tests.test_matcher
python -m tests.test_store
```
