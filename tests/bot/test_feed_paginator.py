from unittest.mock import AsyncMock
from datetime import datetime, timezone
from lilwman.domain.feed_entities import FeedPost, FeedSubscription
from lilwman.bot.feed_paginator import FeedImagePaginator


def _make_subscription(platform="instagram") -> FeedSubscription:
    return FeedSubscription(
        id=1, channel_id="111", platform=platform,
        account_name="testuser", rss_url="http://example.com",
        created_at=datetime.now(timezone.utc),
    )


def _make_post(num_images: int) -> FeedPost:
    return FeedPost(
        guid="p1", title="Test Post", url="https://instagram.com/p/1",
        description="desc", author="testuser",
        published_at=datetime.now(timezone.utc),
        images=[f"https://example.com/img{i}.jpg" for i in range(num_images)],
    )


def test_total_pages_three_images():
    pag = FeedImagePaginator(_make_post(3), _make_subscription())
    assert pag.total_pages == 3


def test_total_pages_one_image():
    pag = FeedImagePaginator(_make_post(1), _make_subscription())
    assert pag.total_pages == 1


def test_make_embed_shows_first_image():
    pag = FeedImagePaginator(_make_post(2), _make_subscription())
    embed = pag.make_embed(0xE1306C)
    assert embed.image.url == "https://example.com/img0.jpg"


def test_make_embed_footer_shows_page():
    pag = FeedImagePaginator(_make_post(3), _make_subscription())
    embed = pag.make_embed(0xE1306C)
    assert "1/3" in embed.footer.text


def test_make_embed_title_and_url():
    pag = FeedImagePaginator(_make_post(2), _make_subscription())
    embed = pag.make_embed(0xE1306C)
    assert embed.title == "Test Post"
    assert embed.url == "https://instagram.com/p/1"


async def test_next_increments_page():
    pag = FeedImagePaginator(_make_post(3), _make_subscription())
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    await pag.next.callback(interaction)
    assert pag.page == 1
    interaction.response.edit_message.assert_called_once()


async def test_next_clamped_at_last_page():
    pag = FeedImagePaginator(_make_post(2), _make_subscription())
    pag.page = 1
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    await pag.next.callback(interaction)
    assert pag.page == 1
    interaction.response.edit_message.assert_called_once()


async def test_prev_decrements_page():
    pag = FeedImagePaginator(_make_post(3), _make_subscription())
    pag.page = 2
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    await pag.prev.callback(interaction)
    assert pag.page == 1
    interaction.response.edit_message.assert_called_once()


async def test_prev_clamped_at_zero():
    pag = FeedImagePaginator(_make_post(3), _make_subscription())
    pag.page = 0
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    await pag.prev.callback(interaction)
    assert pag.page == 0
    interaction.response.edit_message.assert_called_once()
