"""
Checks for GarageEntry serialization round-trip (no Discord connection needed).
Run: python -m tests.test_store
"""
import json

from src.store import MARKER, GarageEntry, _PAYLOAD_FIELDS


class FakeMessage:
    """Minimal stand-in for discord.Message for parsing tests."""
    def __init__(self, content, attachments=None, mid=12345):
        self.content = content
        self.attachments = attachments or []
        self.id = mid


def test_payload_roundtrip():
    e = GarageEntry(
        user_id=42, username="rider", make="Yamaha", model="MT-07",
        badge="", year=2022, category="Naked", displacement_cc=689,
        matched_at="2026-06-18T00:00:00+00:00",
    )
    payload = e.to_payload()
    assert payload.startswith(MARKER)
    data = json.loads(payload[len(MARKER):])
    assert set(data.keys()) == set(_PAYLOAD_FIELDS)

    parsed = GarageEntry.from_message(FakeMessage(payload))
    assert parsed is not None
    assert parsed.user_id == 42
    assert parsed.make == "Yamaha"
    assert parsed.model == "MT-07"
    assert parsed.year == 2022
    assert parsed.message_id == 12345
    assert parsed.has_photo is False


def test_has_photo_from_attachments():
    e = GarageEntry(user_id=1, username="x", make="Honda", model="Grom")
    parsed = GarageEntry.from_message(
        FakeMessage(e.to_payload(), attachments=[object()]))
    assert parsed.has_photo is True


def test_non_entry_message_ignored():
    assert GarageEntry.from_message(FakeMessage("just a normal chat message")) is None


def test_display_name_and_query():
    e = GarageEntry(user_id=1, username="x", make="Ducati",
                    model="Panigale V4", badge="S", year=2022, category="Sport")
    assert e.display_name == "Ducati Panigale V4 S (2022)"
    assert e.matches_query("panigale")
    assert e.matches_query("ducati")
    assert not e.matches_query("yamaha")


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
