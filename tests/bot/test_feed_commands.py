from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import discord
from lilwman.domain.feed_entities import FeedSubscription
from lilwman.bot.commands.feed import FeedCog


def _make_sub(id=1, platform="instagram", account="testuser") -> FeedSubscription:
    return FeedSubscription(
        id=id, channel_id="999", platform=platform,
        account_name=account, rss_url="http://example.com",
        created_at=datetime.now(timezone.utc),
    )


def _make_bot(add_feed=None, remove_feed=None, list_feeds=None):
    bot = MagicMock()
    bot.add_feed = add_feed or AsyncMock()
    bot.remove_feed = remove_feed or AsyncMock()
    bot.list_feeds = list_feeds or AsyncMock()
    return bot


def _make_interaction(is_admin=True, channel_id=999, guild_id=111):
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = is_admin
    interaction.channel_id = channel_id
    interaction.guild_id = guild_id
    interaction.response = AsyncMock()
    return interaction


async def test_feed_add_success():
    add_uc = AsyncMock()
    add_uc.execute = AsyncMock(return_value=_make_sub())
    cog = FeedCog(_make_bot(add_feed=add_uc))
    interaction = _make_interaction()

    await cog.feed_add.callback(cog, interaction, platform="instagram", account="testuser")

    add_uc.execute.assert_called_once_with("999", "instagram", "testuser", guild_id="111")
    call_str = str(interaction.response.send_message.call_args)
    assert "testuser" in call_str


async def test_feed_add_non_admin_denied():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction(is_admin=False)

    await cog.feed_add.callback(cog, interaction, platform="instagram", account="testuser")

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "administrator" in call_str or "permission" in call_str


async def test_feed_add_unknown_platform_reports_error():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction()

    await cog.feed_add.callback(cog, interaction, platform="myspace", account="user")

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "unknown" in call_str or "myspace" in call_str


async def test_feed_add_duplicate_reports_already_subscribed():
    add_uc = AsyncMock()
    add_uc.execute = AsyncMock(return_value=None)
    cog = FeedCog(_make_bot(add_feed=add_uc))
    interaction = _make_interaction()

    await cog.feed_add.callback(cog, interaction, platform="instagram", account="testuser")

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "already" in call_str


async def test_feed_addurl_success():
    add_uc = AsyncMock()
    add_uc.execute_custom_url = AsyncMock(return_value=_make_sub(platform="custom"))
    cog = FeedCog(_make_bot(add_feed=add_uc))
    interaction = _make_interaction()

    await cog.feed_addurl.callback(cog, interaction, url="https://example.com/feed.xml")

    add_uc.execute_custom_url.assert_called_once_with("999", "https://example.com/feed.xml", guild_id="111")


async def test_feed_addurl_non_admin_denied():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction(is_admin=False)

    await cog.feed_addurl.callback(cog, interaction, url="https://example.com/feed.xml")

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "administrator" in call_str or "permission" in call_str


async def test_feed_remove_success():
    remove_uc = AsyncMock()
    remove_uc.execute = AsyncMock(return_value=True)
    cog = FeedCog(_make_bot(remove_feed=remove_uc))
    interaction = _make_interaction()

    await cog.feed_remove.callback(cog, interaction, id=5)

    remove_uc.execute.assert_called_once_with(5, "999")
    call_str = str(interaction.response.send_message.call_args)
    assert "#5" in call_str


async def test_feed_remove_not_found():
    remove_uc = AsyncMock()
    remove_uc.execute = AsyncMock(return_value=False)
    cog = FeedCog(_make_bot(remove_feed=remove_uc))
    interaction = _make_interaction()

    await cog.feed_remove.callback(cog, interaction, id=99)

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "not found" in call_str


async def test_feed_remove_non_admin_denied():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction(is_admin=False)

    await cog.feed_remove.callback(cog, interaction, id=1)

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "administrator" in call_str or "permission" in call_str


async def test_feed_list_shows_subscriptions():
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[_make_sub(1), _make_sub(2, "twitter", "news")])
    cog = FeedCog(_make_bot(list_feeds=list_uc))
    interaction = _make_interaction()

    await cog.feed_list.callback(cog, interaction)

    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs
    embed = kwargs["embed"]
    assert len(embed.fields) == 2


async def test_feed_list_empty_channel():
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[])
    cog = FeedCog(_make_bot(list_feeds=list_uc))
    interaction = _make_interaction()

    await cog.feed_list.callback(cog, interaction)

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "no feeds" in call_str


async def test_feed_list_non_admin_denied():
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[])
    cog = FeedCog(_make_bot(list_feeds=list_uc))
    interaction = _make_interaction(is_admin=False)

    await cog.feed_list.callback(cog, interaction)

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "administrator" in call_str or "permission" in call_str


async def test_feed_add_in_dm_denied():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction(is_admin=True, channel_id=999)
    interaction.guild_id = None  # simulate DM

    await cog.feed_add.callback(cog, interaction, platform="instagram", account="testuser")

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "server" in call_str or "guild" in call_str


async def test_feed_addurl_in_dm_denied():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction(is_admin=True, channel_id=999)
    interaction.guild_id = None  # simulate DM

    await cog.feed_addurl.callback(cog, interaction, url="https://example.com/feed.xml")

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "server" in call_str or "guild" in call_str


async def test_feed_remove_in_dm_denied():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction(is_admin=True, channel_id=999)
    interaction.guild_id = None  # simulate DM

    await cog.feed_remove.callback(cog, interaction, id=1)

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "server" in call_str or "guild" in call_str


async def test_feed_list_in_dm_denied():
    cog = FeedCog(_make_bot())
    interaction = _make_interaction(is_admin=True, channel_id=999)
    interaction.guild_id = None  # simulate DM

    await cog.feed_list.callback(cog, interaction)

    call_str = str(interaction.response.send_message.call_args).lower()
    assert "server" in call_str or "guild" in call_str
