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
│   ├── build_seed.py       # generates data/bikes.csv from a curated spec
│   ├── fetch_dataset.py    # OPTIONAL: enrich dataset from API Ninjas
│   └── bikes.csv           # generated dataset
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

# dataset ships generated, but you can rebuild it any time:
python data/build_seed.py

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

## Expanding the dataset

`data/bikes.csv` ships with ~1,700 rows (17 makes, real model lineups expanded
across year ranges). To grow it:

- **Edit the curated spec** in `data/build_seed.py` and re-run it, or
- **Pull from API Ninjas** (free tier): get a key at https://api-ninjas.com,
  then `export API_NINJAS_KEY=your_key && python data/fetch_dataset.py`.

## Tests

```bash
python -m tests.test_matcher
python -m tests.test_store
```
