"""
bot.py
======
Discord bot for "what do you ride?".

Flow:
  /whatiride       -> modal (make/model/badge/year) -> fuzzy match -> confirm
                      button -> saves the bike to your garage (a private
                      archive channel, no local files).
  /garage show     -> show a member's bikes, with photos.
  /garage photo    -> attach/replace a photo for one of your bikes.
  /garage remove   -> remove one of your bikes.
  /whorides <q>    -> who in the server rides a given make/model.
  /roster          -> summary of what everyone rides.

Run:
    python bot.py
"""
from __future__ import annotations

import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from src.dataset import load_records
from src.matcher import BikeMatcher, MatchResult
from src.store import ArchiveStore, GarageEntry, now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("whatiride")

load_dotenv()

TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
GUILD_ID = os.environ.get("GUILD_ID", "").strip()
GARAGE_CHANNEL_ID = os.environ.get("GARAGE_CHANNEL_ID", "").strip()
GARAGE_CHANNEL_NAME = os.environ.get("GARAGE_CHANNEL_NAME", "garage-archive").strip()
ENABLE_MAKE_ROLE = os.environ.get("ENABLE_MAKE_ROLE", "false").lower() in ("1", "true", "yes")
ROLE_PREFIX = os.environ.get("ROLE_PREFIX", "")
try:
    MIN_CONFIDENCE = float(os.environ.get("MIN_CONFIDENCE", "55"))
except ValueError:
    MIN_CONFIDENCE = 55.0


# --------------------------------------------------------------------------- #
# Optional make-role assignment (off by default; the garage store is primary)
# --------------------------------------------------------------------------- #
async def maybe_assign_make_role(interaction: discord.Interaction,
                                 entry: GarageEntry) -> str | None:
    if not ENABLE_MAKE_ROLE:
        return None
    guild = interaction.guild
    member = interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return None
    name = f"{ROLE_PREFIX}{entry.make}"
    role = discord.utils.get(guild.roles, name=name)
    me = guild.me
    if not me.guild_permissions.manage_roles:
        return "(couldn't add a make role: missing Manage Roles)"
    try:
        if role is None:
            role = await guild.create_role(name=name, mentionable=True,
                                           reason="whatiride make role")
        if role >= me.top_role:
            return f"(couldn't add **{name}**: my role is below it)"
        if role not in member.roles:
            await member.add_roles(role, reason="whatiride make role")
        return f"Added the **{name}** role."
    except discord.HTTPException:
        return "(couldn't add a make role)"


# --------------------------------------------------------------------------- #
# /whatiride match UI
# --------------------------------------------------------------------------- #
def build_results_embed(results: list[MatchResult]) -> discord.Embed:
    best = results[0]
    confident = best.score >= MIN_CONFIDENCE
    rec = best.record
    embed = discord.Embed(
        title=f"{'Closest match' if confident else 'Best guess (low confidence)'}: "
              f"{rec.display_name}",
        colour=discord.Colour.green() if confident else discord.Colour.orange(),
    )
    embed.add_field(name="Make", value=rec.make, inline=True)
    embed.add_field(name="Model",
                    value=rec.model + (f" {rec.badge}" if rec.badge else ""), inline=True)
    embed.add_field(name="Year", value=best.matched_year_text, inline=True)
    embed.add_field(name="Type", value=rec.category or "—", inline=True)
    embed.add_field(name="Engine",
                    value=f"{rec.displacement_cc}cc" if rec.displacement_cc else "—",
                    inline=True)
    embed.add_field(name="Confidence", value=f"{best.score:.0f}%", inline=True)
    if len(results) > 1:
        embed.add_field(
            name="Other possibilities",
            value="\n".join(f"• {r.record.display_name} ({r.score:.0f}%)"
                            for r in results[1:]),
            inline=False,
        )
    embed.set_footer(text="Pick the button that matches your bike to add it to your garage.")
    return embed


class ConfirmView(discord.ui.View):
    def __init__(self, bot: "WhatIRideBot", results: list[MatchResult], owner_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.owner_id = owner_id
        for i, result in enumerate(results):
            self.add_item(self._make_button(result, primary=(i == 0)))

    def _make_button(self, result: MatchResult, primary: bool) -> discord.ui.Button:
        label = result.record.display_name[:80]
        button = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.success if primary else discord.ButtonStyle.secondary,
        )

        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message(
                    "Only the person who ran the command can choose.", ephemeral=True)
                return
            rec = result.record
            # Avoid duplicates of the exact same bike for this user.
            existing = [
                e for e in self.bot.store.user_entries(interaction.user.id)
                if e.make.lower() == rec.make.lower()
                and e.model.lower() == rec.model.lower()
                and e.badge.lower() == rec.badge.lower()
            ]
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)

            if existing:
                await interaction.followup.send(
                    f"You already have **{rec.display_name}** in your garage. "
                    "Add a photo with `/garage photo`.", ephemeral=True)
                return

            entry = GarageEntry(
                user_id=interaction.user.id,
                username=interaction.user.display_name,
                make=rec.make, model=rec.model, badge=rec.badge,
                year=result.requested_year if (result.requested_year
                     and rec.covers_year(result.requested_year)) else None,
                category=rec.category, displacement_cc=rec.displacement_cc,
                matched_at=now_iso(),
            )
            try:
                await self.bot.store.add(entry)
            except discord.HTTPException as exc:
                await interaction.followup.send(
                    f"Couldn't save to the garage channel: {exc}", ephemeral=True)
                return

            role_msg = await maybe_assign_make_role(interaction, entry)
            msg = (f"Added **{rec.display_name}** to your garage 🏍️\n"
                   "Show it off with a photo: `/garage photo`.")
            if role_msg:
                msg += f"\n{role_msg}"
            await interaction.followup.send(msg, ephemeral=True)

        button.callback = callback  # type: ignore[assignment]
        return button


class WhatIRideModal(discord.ui.Modal, title="What do you ride?"):
    make = discord.ui.TextInput(label="Make", placeholder="e.g. Honda, Yamaha, Ducati",
                                required=True, max_length=40)
    model = discord.ui.TextInput(label="Model", placeholder="e.g. CBR1000RR, MT-07",
                                 required=True, max_length=60)
    badge = discord.ui.TextInput(label="Badge / variant (optional)",
                                 placeholder="e.g. Fireblade, RS, SP, Factory",
                                 required=False, max_length=40)
    year = discord.ui.TextInput(label="Year (optional)", placeholder="e.g. 2021",
                                required=False, max_length=4)

    def __init__(self, bot: "WhatIRideBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        raw_year = str(self.year.value).strip()
        year_val = int(raw_year) if raw_year.isdigit() else None
        results = self.bot.matcher.match(
            make=str(self.make.value), model=str(self.model.value),
            badge=str(self.badge.value), year=year_val, limit=3)
        if not results or results[0].score <= 0:
            await interaction.response.send_message(
                "I couldn't find anything close to that. Try a different spelling "
                "or a more common model name.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=build_results_embed(results),
            view=ConfirmView(self.bot, results, interaction.user.id),
            ephemeral=True)


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class WhatIRideBot(discord.Client):
    def __init__(self, matcher: BikeMatcher):
        super().__init__(intents=discord.Intents.default())
        self.matcher = matcher
        self.tree = app_commands.CommandTree(self)
        channel_id = int(GARAGE_CHANNEL_ID) if GARAGE_CHANNEL_ID.isdigit() else None
        self.store = ArchiveStore(self, channel_id, GARAGE_CHANNEL_NAME)
        self._store_ready = False

    async def setup_hook(self):
        self._register_commands()
        if GUILD_ID.isdigit():
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to guild %s", GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Synced commands globally (may take up to ~1h to appear).")

    async def on_ready(self):
        log.info("Logged in as %s (%s servers)", self.user, len(self.guilds))
        if self._store_ready:
            return
        guild = None
        if GUILD_ID.isdigit():
            guild = self.get_guild(int(GUILD_ID))
        if guild is None and self.guilds:
            guild = self.guilds[0]
        if guild is None:
            log.warning("No guild available yet; garage store not initialized.")
            return
        try:
            ch = await self.store.ensure_channel(guild)
            count = await self.store.load()
            self._store_ready = True
            log.info("Garage store ready in #%s (%d entries).", ch.name, count)
        except discord.Forbidden:
            log.error("Missing permissions to create/read the garage channel. "
                      "Grant 'Manage Channels' or set GARAGE_CHANNEL_ID.")
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to init garage store: %s", exc)

    # -- command registration --------------------------------------------- #
    def _register_commands(self):
        bot = self

        @self.tree.command(name="whatiride",
                           description="Tell us what you ride and add it to your garage.")
        async def whatiride(interaction: discord.Interaction):
            await interaction.response.send_modal(WhatIRideModal(bot))

        garage = app_commands.Group(name="garage", description="Your bike garage")

        @garage.command(name="show", description="Show a rider's garage (defaults to you).")
        @app_commands.describe(user="Whose garage to show (optional)")
        async def garage_show(interaction: discord.Interaction,
                              user: discord.Member | None = None):
            target = user or interaction.user
            entries = bot.store.user_entries(target.id)
            if not entries:
                who = "You have" if target.id == interaction.user.id else f"{target.display_name} has"
                await interaction.response.send_message(
                    f"{who} no bikes in the garage yet. Use `/whatiride` to add one.",
                    ephemeral=True)
                return
            await interaction.response.defer(ephemeral=False)
            embeds = []
            for e in entries[:10]:
                emb = e.build_embed()
                if e.message_id is not None:
                    url = await bot.store.photo_url(e.message_id)
                    if url:
                        emb.set_image(url=url)
                embeds.append(emb)
            header = f"🏍️ {target.display_name}'s garage ({len(entries)} bike(s))"
            await interaction.followup.send(content=header, embeds=embeds)

        @garage.command(name="photo", description="Add or replace a photo for one of your bikes.")
        @app_commands.describe(bike="Which bike", image="The photo to attach")
        async def garage_photo(interaction: discord.Interaction,
                               bike: str, image: discord.Attachment):
            entry = bot.store.entries.get(int(bike)) if bike.isdigit() else None
            if entry is None or entry.user_id != interaction.user.id:
                await interaction.response.send_message(
                    "Pick one of your own bikes from the list.", ephemeral=True)
                return
            if not (image.content_type or "").startswith("image/"):
                await interaction.response.send_message(
                    "That file doesn't look like an image.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            try:
                file = await image.to_file()
                await bot.store.set_photo(entry, file)
            except discord.HTTPException as exc:
                await interaction.followup.send(f"Couldn't save the photo: {exc}",
                                                ephemeral=True)
                return
            await interaction.followup.send(
                f"Photo set for **{entry.display_name}**. View it with `/garage show`.",
                ephemeral=True)

        @garage.command(name="remove", description="Remove one of your bikes.")
        @app_commands.describe(bike="Which bike to remove")
        async def garage_remove(interaction: discord.Interaction, bike: str):
            entry = bot.store.entries.get(int(bike)) if bike.isdigit() else None
            if entry is None or entry.user_id != interaction.user.id:
                await interaction.response.send_message(
                    "Pick one of your own bikes from the list.", ephemeral=True)
                return
            await bot.store.remove(entry.message_id)  # type: ignore[arg-type]
            await interaction.response.send_message(
                f"Removed **{entry.display_name}** from your garage.", ephemeral=True)

        # Autocomplete: list the caller's own bikes for photo/remove.
        async def own_bike_autocomplete(interaction: discord.Interaction, current: str):
            entries = bot.store.user_entries(interaction.user.id)
            current = current.lower()
            choices = []
            for e in entries:
                if current and current not in e.display_name.lower():
                    continue
                choices.append(app_commands.Choice(
                    name=e.display_name[:100], value=str(e.message_id)))
            return choices[:25]

        garage_photo.autocomplete("bike")(own_bike_autocomplete)
        garage_remove.autocomplete("bike")(own_bike_autocomplete)
        self.tree.add_command(garage)

        @self.tree.command(name="whorides",
                           description="See who rides a given make or model.")
        @app_commands.describe(query="Make or model, e.g. Ducati or MT-07")
        async def whorides(interaction: discord.Interaction, query: str):
            matches = bot.store.search(query)
            if not matches:
                await interaction.response.send_message(
                    f"Nobody has a bike matching “{query}” yet.", ephemeral=True)
                return
            lines = [f"• <@{e.user_id}> — {e.display_name}" for e in matches[:30]]
            extra = "" if len(matches) <= 30 else f"\n…and {len(matches) - 30} more."
            embed = discord.Embed(
                title=f"Riders matching “{query}” ({len(matches)})",
                description="\n".join(lines) + extra,
                colour=discord.Colour.blurple())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="roster",
                           description="Summary of what everyone rides.")
        async def roster(interaction: discord.Interaction):
            entries = bot.store.all()
            if not entries:
                await interaction.response.send_message(
                    "The garage is empty. Be the first with `/whatiride`!",
                    ephemeral=True)
                return
            by_make: dict[str, int] = {}
            riders: set[int] = set()
            for e in entries:
                by_make[e.make] = by_make.get(e.make, 0) + 1
                riders.add(e.user_id)
            ranked = sorted(by_make.items(), key=lambda kv: kv[1], reverse=True)
            lines = [f"• **{make}** — {n}" for make, n in ranked[:15]]
            embed = discord.Embed(
                title="🏍️ Server roster",
                description=(f"**{len(entries)} bikes** across **{len(riders)} riders**\n\n"
                            + "\n".join(lines)),
                colour=discord.Colour.blurple())
            await interaction.response.send_message(embed=embed)


def main():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env "
                         "and add your token.")
    records = load_records()
    log.info("Loaded %d bike records.", len(records))
    bot = WhatIRideBot(BikeMatcher(records))
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
