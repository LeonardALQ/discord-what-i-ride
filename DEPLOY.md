# Deploying whatiride-bot to a hobby PaaS

The bot is a **worker** — it makes outbound connections to Discord and listens
on no port. Because all data lives in the Discord archive channel, the host
needs **no persistent disk or database**. Pick whichever platform you like.

> Do NOT commit your `.env` / token. `.gitignore` already excludes `.env`.
> Set secrets in the platform's dashboard/CLI instead.

---

## Option A — Railway (easiest for testing)

1. Push this project to a GitHub repo (token stays local thanks to `.gitignore`).
2. Go to https://railway.app → **New Project → Deploy from GitHub repo** and
   pick the repo. Railway builds it from the `Dockerfile` automatically.
3. Open the service → **Variables** and add:
   - `DISCORD_TOKEN` = your bot token
   - `GUILD_ID` = your server ID
   - (optional) `GARAGE_CHANNEL_ID`, `ENABLE_MAKE_ROLE`, etc.
4. Railway runs the container's `CMD` (`python bot.py`) as a long-running
   service. **Do not** add a public domain/port — it's a worker, not a website.
5. Check the **Deploy logs**; you should see "Logged in as ..." and
   "Garage store ready in #garage-archive".

To redeploy, just `git push` — Railway rebuilds automatically.

---

## Option B — Fly.io

Prereqs: install `flyctl` and run `fly auth login`.

```bash
# from the project directory (fly.toml is already provided)
fly launch --no-deploy        # accept the existing fly.toml; pick an app name/region
fly secrets set DISCORD_TOKEN=your-token GUILD_ID=your-guild-id
fly deploy
fly logs                      # watch it connect
```

`fly.toml` is preconfigured as a worker (no `[http_service]`), so Fly won't try
to health-check an HTTP port. Adjust `primary_region` to your nearest region.

---

## Sanity checklist

- Bot invited with scopes `bot` + `applications.commands`, and permissions:
  **Manage Channels** (once, to auto-create the archive channel), **Send
  Messages**, **Embed Links**, **Attach Files**, **Read Message History**.
- `GUILD_ID` set so slash commands appear instantly.
- Logs show login + "Garage store ready".
- In Discord, run `/whatiride` → confirm a match → `/garage photo` → `/garage show`.

## Notes for free tiers

- Use a **worker / background** process, not a "web service" — free web tiers
  that **sleep on idle** will drop the bot's connection.
- Free tiers may cap monthly hours; a single small worker is usually fine for
  testing. Move to a paid tier (or a $5 VPS) when you go live.
