from unittest.mock import AsyncMock, MagicMock, patch
from lilwman.infrastructure.http.feed_fetcher import AiohttpFeedFetcher, _parse_feed

ATOM_WITH_IMAGE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:media="http://search.yahoo.com/mrss/">
  <entry>
    <id>post-001</id>
    <title>Hello World</title>
    <link href="https://instagram.com/p/001"/>
    <summary>A test post &lt;b&gt;bold&lt;/b&gt;</summary>
    <author><name>testuser</name></author>
    <published>2026-06-21T10:00:00Z</published>
    <media:content url="https://example.com/img1.jpg" medium="image"/>
  </entry>
</feed>"""

ATOM_EMPTY = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

ATOM_TWO_ENTRIES = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>p1</id>
    <title>Post 1</title>
    <link href="https://example.com/p1"/>
    <published>2026-06-21T09:00:00Z</published>
  </entry>
  <entry>
    <id>p2</id>
    <title>Post 2</title>
    <link href="https://example.com/p2"/>
    <published>2026-06-21T10:00:00Z</published>
  </entry>
</feed>"""


def test_parse_feed_returns_one_post():
    posts = _parse_feed(ATOM_WITH_IMAGE)
    assert len(posts) == 1


def test_parse_feed_post_fields():
    posts = _parse_feed(ATOM_WITH_IMAGE)
    post = posts[0]
    assert post.guid == "post-001"
    assert post.title == "Hello World"
    assert post.url == "https://instagram.com/p/001"
    assert post.author == "testuser"


def test_parse_feed_strips_html_from_description():
    posts = _parse_feed(ATOM_WITH_IMAGE)
    assert "<b>" not in posts[0].description
    assert "bold" in posts[0].description


def test_parse_feed_extracts_image():
    posts = _parse_feed(ATOM_WITH_IMAGE)
    assert posts[0].images == ["https://example.com/img1.jpg"]


def test_parse_feed_no_video():
    posts = _parse_feed(ATOM_WITH_IMAGE)
    assert posts[0].video_url is None


def test_parse_feed_empty_returns_empty_list():
    posts = _parse_feed(ATOM_EMPTY)
    assert posts == []


def test_parse_feed_two_entries():
    posts = _parse_feed(ATOM_TWO_ENTRIES)
    assert len(posts) == 2
    guids = {p.guid for p in posts}
    assert guids == {"p1", "p2"}


def test_parse_feed_missing_image_returns_empty_list():
    posts = _parse_feed(ATOM_TWO_ENTRIES)
    assert posts[0].images == []
    assert posts[0].video_url is None


async def test_fetch_calls_url_and_returns_posts():
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = AsyncMock(return_value=ATOM_WITH_IMAGE)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("lilwman.infrastructure.http.feed_fetcher.aiohttp.ClientSession",
               return_value=mock_session):
        fetcher = AiohttpFeedFetcher()
        posts = await fetcher.fetch("http://localhost:3000/test")

    assert len(posts) == 1
    mock_session.get.assert_called_once_with("http://localhost:3000/test")
