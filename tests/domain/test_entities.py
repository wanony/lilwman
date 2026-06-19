from datetime import datetime, timezone
from lilwman.domain.entities import Entry


def test_entry_has_expected_fields():
    now = datetime.now(timezone.utc)
    entry = Entry(
        id=1,
        content="some content",
        tags=["python", "nix"],
        author_id="123456789",
        author_name="cameron",
        created_at=now,
        updated_at=now,
    )
    assert entry.id == 1
    assert entry.content == "some content"
    assert entry.tags == ["python", "nix"]
    assert entry.author_id == "123456789"
    assert entry.author_name == "cameron"


def test_entry_tags_defaults_to_empty_list():
    now = datetime.now(timezone.utc)
    entry = Entry(
        id=2,
        content="no tags",
        tags=[],
        author_id="111",
        author_name="user",
        created_at=now,
        updated_at=now,
    )
    assert entry.tags == []
