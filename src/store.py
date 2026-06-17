"""
store.py
========
A datastore backed entirely by a private Discord channel. No local files.

Each garage entry is one message in the archive channel:
  - message content: a machine-readable JSON payload (prefixed with MARKER)
  - an embed: human-readable summary (so the channel is browsable)
  - an optional image attachment: the bike photo (lives on Discord's CDN)

On startup the bot reads the channel into an in-memory cache. Writes update
both Discord and the cache. Photo URLs are re-fetched live when displaying, so
Discord's expiring attachment URLs are never stored or stale.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import discord

MARKER = "GARAGE_ENTRY_V1 "

# Fields persisted in the JSON payload (message_id/has_photo are derived).
_PAYLOAD_FIELDS = (
    "user_id", "username", "make", "model", "badge",
    "year", "category", "displacement_cc", "matched_at",
)


@dataclass
class GarageEntry:
    user_id: int
    username: str
    make: str
    model: str
    badge: str = ""
    year: int | None = None
    category: str = ""
    displacement_cc: int = 0
    matched_at: str = ""
    message_id: int | None = field(default=None)
    has_photo: bool = field(default=False)

    @property
    def display_name(self) -> str:
        parts = [self.make, self.model]
        if self.badge:
            parts.append(self.badge)
        name = " ".join(p for p in parts if p)
        if self.year:
            name += f" ({self.year})"
        return name

    def matches_query(self, q: str) -> bool:
        q = q.lower().strip()
        hay = f"{self.make} {self.model} {self.badge} {self.category}".lower()
        return q in hay

    def to_payload(self) -> str:
        data = {k: getattr(self, k) for k in _PAYLOAD_FIELDS}
        return MARKER + json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_message(cls, msg: discord.Message) -> "GarageEntry | None":
        if not msg.content.startswith(MARKER):
            return None
        try:
            data = json.loads(msg.content[len(MARKER):])
        except (ValueError, json.JSONDecodeError):
            return None
        kwargs = {k: data.get(k) for k in _PAYLOAD_FIELDS}
        return cls(
            message_id=msg.id,
            has_photo=bool(msg.attachments),
            **kwargs,
        )

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.display_name, colour=discord.Colour.blue())
        embed.add_field(name="Rider", value=self.username or f"<@{self.user_id}>")
        if self.category:
            embed.add_field(name="Type", value=self.category)
        if self.displacement_cc:
            embed.add_field(name="Engine", value=f"{self.displacement_cc}cc")
        return embed


class ArchiveStore:
    """Manages one private archive channel within a single guild."""

    def __init__(self, client: discord.Client, channel_id: int | None,
                 channel_name: str = "garage-archive"):
        self.client = client
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.channel: discord.TextChannel | None = None
        # message_id -> GarageEntry
        self.entries: dict[int, GarageEntry] = {}

    # -- setup ------------------------------------------------------------- #
    async def ensure_channel(self, guild: discord.Guild) -> discord.TextChannel:
        if self.channel_id:
            ch = guild.get_channel(self.channel_id) or await self.client.fetch_channel(
                self.channel_id
            )
            if not isinstance(ch, discord.TextChannel):
                raise RuntimeError("GARAGE_CHANNEL_ID is not a text channel.")
            self.channel = ch
            return ch

        existing = discord.utils.get(guild.text_channels, name=self.channel_name)
        if existing:
            self.channel = existing
            return existing

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_messages=True, read_message_history=True,
                attach_files=True,
            ),
        }
        ch = await guild.create_text_channel(
            self.channel_name, overwrites=overwrites,
            reason="whatiride: private garage datastore",
            topic="Bot-managed garage data. Do not edit messages here.",
        )
        self.channel = ch
        return ch

    async def load(self) -> int:
        """Read the channel into the in-memory cache. Returns entry count."""
        if self.channel is None:
            raise RuntimeError("Channel not initialized; call ensure_channel first.")
        self.entries.clear()
        async for msg in self.channel.history(limit=None, oldest_first=True):
            entry = GarageEntry.from_message(msg)
            if entry and entry.message_id is not None:
                self.entries[entry.message_id] = entry
        return len(self.entries)

    # -- writes ------------------------------------------------------------ #
    async def add(self, entry: GarageEntry,
                  file: discord.File | None = None) -> GarageEntry:
        assert self.channel is not None
        msg = await self.channel.send(
            content=entry.to_payload(),
            embed=entry.build_embed(),
            file=file,
        )
        entry.message_id = msg.id
        entry.has_photo = bool(msg.attachments)
        self.entries[msg.id] = entry
        return entry

    async def set_photo(self, entry: GarageEntry, file: discord.File) -> GarageEntry:
        """Replace the entry's photo by reposting (so the attachment is set)."""
        assert self.channel is not None and entry.message_id is not None
        old_id = entry.message_id
        new = await self.channel.send(
            content=entry.to_payload(),
            embed=entry.build_embed(),
            file=file,
        )
        # Remove the old message after the new one lands.
        old = self.entries.pop(old_id, None)
        try:
            old_msg = await self.channel.fetch_message(old_id)
            await old_msg.delete()
        except discord.HTTPException:
            pass
        entry.message_id = new.id
        entry.has_photo = True
        self.entries[new.id] = entry
        return entry

    async def remove(self, message_id: int) -> bool:
        assert self.channel is not None
        if message_id not in self.entries:
            return False
        self.entries.pop(message_id, None)
        try:
            msg = await self.channel.fetch_message(message_id)
            await msg.delete()
        except discord.HTTPException:
            pass
        return True

    async def photo_url(self, message_id: int) -> str | None:
        """Fetch a fresh (non-expired) attachment URL for an entry."""
        assert self.channel is not None
        try:
            msg = await self.channel.fetch_message(message_id)
        except discord.HTTPException:
            return None
        if msg.attachments:
            return msg.attachments[0].url
        return None

    # -- reads ------------------------------------------------------------- #
    def user_entries(self, user_id: int) -> list[GarageEntry]:
        return [e for e in self.entries.values() if e.user_id == user_id]

    def search(self, query: str) -> list[GarageEntry]:
        return [e for e in self.entries.values() if e.matches_query(query)]

    def all(self) -> list[GarageEntry]:
        return list(self.entries.values())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
