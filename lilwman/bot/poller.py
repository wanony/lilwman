import logging

import discord
from discord.ext import commands, tasks

from lilwman.application.poll_feeds import PollFeedsUseCase
from lilwman.bot.feed_paginator import FeedImagePaginator
from lilwman.bot.feed_utils import get_fix_url, get_platform_colour
from lilwman.domain.feed_entities import FeedPost, FeedSubscription

log = logging.getLogger(__name__)


class FeedPoller(commands.Cog):
    def __init__(self, bot, poll_feeds: PollFeedsUseCase) -> None:
        self.bot = bot
        self.poll_feeds = poll_feeds

    async def cog_load(self) -> None:
        self._poll_loop.start()

    def cog_unload(self) -> None:
        self._poll_loop.cancel()

    @tasks.loop(minutes=5)
    async def _poll_loop(self) -> None:
        await self._do_poll()

    @_poll_loop.before_loop
    async def _before_poll(self) -> None:
        await self.bot.wait_until_ready()

    async def _do_poll(self) -> None:
        try:
            results = await self.poll_feeds.execute()
        except Exception:
            log.exception("Feed poll error")
            return
        for sub, posts in results:
            for post in posts:
                await self._post(sub, post)

    async def _post(self, sub: FeedSubscription, post: FeedPost) -> None:
        channel = self.bot.get_channel(int(sub.channel_id))
        if channel is None:
            log.warning("Channel %s not found for feed %s", sub.channel_id, sub.id)
            return
        try:
            colour = get_platform_colour(sub.platform)
            if post.video_url:
                fix = get_fix_url(sub.platform, post.url)
                if fix:
                    await channel.send(fix)
                    return
            if len(post.images) > 1:
                paginator = FeedImagePaginator(post, sub)
                await channel.send(embed=paginator.make_embed(colour), view=paginator)
                return
            if post.images:
                embed = _make_post_embed(post, sub, colour)
                embed.set_image(url=post.images[0])
                await channel.send(embed=embed)
                return
            await channel.send(embed=_make_post_embed(post, sub, colour))
        except Exception:
            log.warning("Failed to post to channel %s", sub.channel_id, exc_info=True)


def _make_post_embed(
    post: FeedPost, sub: FeedSubscription, colour: int
) -> discord.Embed:
    embed = discord.Embed(
        title=post.title,
        url=post.url,
        description=post.description,
        color=colour,
    )
    embed.set_author(name=f"@{sub.account_name} on {sub.platform}")
    embed.timestamp = post.published_at
    return embed
