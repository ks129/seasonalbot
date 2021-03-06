import asyncio
import itertools
import json
import logging
import random
import typing as t
from datetime import datetime, time, timedelta
from pathlib import Path

import arrow
import discord
from discord.embeds import EmptyEmbed
from discord.ext import commands

from bot.bot import SeasonalBot
from bot.constants import Branding, Colours, Emojis, MODERATION_ROLES, Tokens
from bot.seasons import SeasonBase, get_all_seasons, get_current_season, get_season
from bot.utils import human_months
from bot.utils.decorators import with_role
from bot.utils.exceptions import BrandingError
# TODO: Implement substitute for current volume persistence requirements
# from bot.utils.persist import make_persistent

log = logging.getLogger(__name__)

STATUS_OK = 200  # HTTP status code

FILE_BANNER = "banner.png"
FILE_AVATAR = "avatar.png"
SERVER_ICONS = "server_icons"

BRANDING_URL = "https://api.github.com/repos/python-discord/branding/contents"

PARAMS = {"ref": "master"}  # Target branch
HEADERS = {"Accept": "application/vnd.github.v3+json"}  # Ensure we use API v3

# A GitHub token is not necessary for the cog to operate,
# unauthorized requests are however limited to 60 per hour
if Tokens.github:
    HEADERS["Authorization"] = f"token {Tokens.github}"


class GitHubFile(t.NamedTuple):
    """
    Represents a remote file on GitHub.

    The `sha` hash is kept so that we can determine that a file has changed,
    despite its filename remaining unchanged.
    """

    download_url: str
    path: str
    sha: str


def pretty_files(files: t.Iterable[GitHubFile]) -> str:
    """Provide a human-friendly representation of `files`."""
    return "\n".join(file.path for file in files)


def time_until_midnight() -> timedelta:
    """
    Determine amount of time until the next-up UTC midnight.

    The exact `midnight` moment is actually delayed to 5 seconds after, in order
    to avoid potential problems due to imprecise sleep.
    """
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)
    midnight = datetime.combine(tomorrow, time(second=5))

    return midnight - now


class BrandingManager(commands.Cog):
    """
    Manages the guild's branding.

    The purpose of this cog is to help automate the synchronization of the branding
    repository with the guild. It is capable of discovering assets in the repository
    via GitHub's API, resolving download urls for them, and delegating
    to the `bot` instance to upload them to the guild.

    BrandingManager is designed to be entirely autonomous. Its `daemon` background task awakens
    once a day (see `time_until_midnight`) to detect new seasons, or to cycle icons within a single
    season. The daemon can be turned on and off via the `daemon` cmd group. The value set via
    its `start` and `stop` commands is persisted across sessions. If turned on, the daemon will
    automatically start on the next bot start-up. Otherwise, it will wait to be started manually.

    All supported operations, e.g. setting seasons, applying the branding, or cycling icons, can
    also be invoked manually, via the following API:

        branding list
            - Show all available seasons

        branding set <season_name>
            - Set the cog's internal state to represent `season_name`, if it exists
            - If no `season_name` is given, set chronologically current season
            - This will not automatically apply the season's branding to the guild,
              the cog's state can be detached from the guild
            - Seasons can therefore be 'previewed' using this command

        branding info
            - View detailed information about resolved assets for current season

        branding refresh
            - Refresh internal state, i.e. synchronize with branding repository

        branding apply
            - Apply the current internal state to the guild, i.e. upload the assets

        branding cycle
            - If there are multiple available icons for current season, randomly pick
              and apply the next one

    The daemon calls these methods autonomously as appropriate. The use of this cog
    is locked to moderation roles. As it performs media asset uploads, it is prone to
    rate-limits - the `apply` command should be used with caution. The `set` command can,
    however, be used freely to 'preview' seasonal branding and check whether paths have been
    resolved as appropriate.

    While the bot is in debug mode, it will 'mock' asset uploads by logging the passed
    download urls and pretending that the upload was successful. Make use of this
    to test this cog's behaviour.
    """

    current_season: t.Type[SeasonBase]

    banner: t.Optional[GitHubFile]
    avatar: t.Optional[GitHubFile]

    available_icons: t.List[GitHubFile]
    remaining_icons: t.List[GitHubFile]

    days_since_cycle: t.Iterator

    config_file: Path

    daemon: t.Optional[asyncio.Task]

    def __init__(self, bot: SeasonalBot) -> None:
        """
        Assign safe default values on init.

        At this point, we don't have information about currently available branding.
        Most of these attributes will be overwritten once the daemon connects, or once
        the `refresh` command is used.
        """
        self.bot = bot
        self.current_season = get_current_season()

        self.banner = None
        self.avatar = None

        self.available_icons = []
        self.remaining_icons = []

        self.days_since_cycle = itertools.cycle([None])

        # self.config_file = make_persistent(Path("bot", "resources", "evergreen", "branding.json"))

        # should_run = self._read_config()["daemon_active"]

        # if should_run:
        #     self.daemon = self.bot.loop.create_task(self._daemon_func())
        # else:
        self.daemon = None

    @property
    def _daemon_running(self) -> bool:
        """True if the daemon is currently active, False otherwise."""
        return self.daemon is not None and not self.daemon.done()

    def _read_config(self) -> t.Dict[str, bool]:
        """Read and return persistent config file."""
        raise NotImplementedError("read_config functionality requires mounting a persistent volume.")

    def _write_config(self, key: str, value: bool) -> None:
        """Write a `key`, `value` pair to persistent config file."""
        raise NotImplementedError("write_config functionality requires mounting a persistent volume.")

    async def _daemon_func(self) -> None:
        """
        Manage all automated behaviour of the BrandingManager cog.

        Once a day, the daemon will perform the following tasks:
            - Update `current_season`
            - Poll GitHub API to see if the available branding for `current_season` has changed
            - Update assets if changes are detected (banner, guild icon, bot avatar, bot nickname)
            - Check whether it's time to cycle guild icons

        The internal loop runs once when activated, then periodically at the time
        given by `time_until_midnight`.

        All method calls in the internal loop are considered safe, i.e. no errors propagate
        to the daemon's loop. The daemon itself does not perform any error handling on its own.
        """
        await self.bot.wait_until_guild_available()

        while True:
            self.current_season = get_current_season()
            branding_changed = await self.refresh()

            if branding_changed:
                await self.apply()

            elif next(self.days_since_cycle) == Branding.cycle_frequency:
                await self.cycle()

            until_midnight = time_until_midnight()
            await asyncio.sleep(until_midnight.total_seconds())

    async def _info_embed(self) -> discord.Embed:
        """Make an informative embed representing current season."""
        info_embed = discord.Embed(description=self.current_season.description, colour=self.current_season.colour)

        # If we're in a non-evergreen season, also show active months
        if self.current_season is not SeasonBase:
            title = f"{self.current_season.season_name} ({human_months(self.current_season.months)})"
        else:
            title = self.current_season.season_name

        # Use the author field to show the season's name and avatar if available
        info_embed.set_author(name=title, icon_url=self.avatar.download_url if self.avatar else EmptyEmbed)

        banner = self.banner.path if self.banner is not None else "Unavailable"
        info_embed.add_field(name="Banner", value=banner, inline=False)

        avatar = self.avatar.path if self.avatar is not None else "Unavailable"
        info_embed.add_field(name="Avatar", value=avatar, inline=False)

        icons = pretty_files(self.available_icons) or "Unavailable"
        info_embed.add_field(name="Available icons", value=icons, inline=False)

        # Only display cycle frequency if we're actually cycling
        if len(self.available_icons) > 1 and Branding.cycle_frequency:
            info_embed.set_footer(text=f"Icon cycle frequency: {Branding.cycle_frequency}")

        return info_embed

    async def _reset_remaining_icons(self) -> None:
        """Set `remaining_icons` to a shuffled copy of `available_icons`."""
        self.remaining_icons = random.sample(self.available_icons, k=len(self.available_icons))

    async def _reset_days_since_cycle(self) -> None:
        """
        Reset the `days_since_cycle` iterator based on configured frequency.

        If the current season only has 1 icon, or if `Branding.cycle_frequency` is falsey,
        the iterator will always yield None. This signals that the icon shouldn't be cycled.

        Otherwise, it will yield ints in range [1, `Branding.cycle_frequency`] indefinitely.
        When the iterator yields a value equal to `Branding.cycle_frequency`, it is time to cycle.
        """
        if len(self.available_icons) > 1 and Branding.cycle_frequency:
            sequence = range(1, Branding.cycle_frequency + 1)
        else:
            sequence = [None]

        self.days_since_cycle = itertools.cycle(sequence)

    async def _get_files(self, path: str, include_dirs: bool = False) -> t.Dict[str, GitHubFile]:
        """
        Get files at `path` in the branding repository.

        If `include_dirs` is False (default), only returns files at `path`.
        Otherwise, will return both files and directories. Never returns symlinks.

        Return dict mapping from filename to corresponding `GitHubFile` instance.
        This may return an empty dict if the response status is non-200,
        or if the target directory is empty.
        """
        url = f"{BRANDING_URL}/{path}"
        async with self.bot.http_session.get(url, headers=HEADERS, params=PARAMS) as resp:
            # Short-circuit if we get non-200 response
            if resp.status != STATUS_OK:
                log.error(f"GitHub API returned non-200 response: {resp}")
                return {}
            directory = await resp.json()  # Directory at `path`

        allowed_types = {"file", "dir"} if include_dirs else {"file"}
        return {
            file["name"]: GitHubFile(file["download_url"], file["path"], file["sha"])
            for file in directory
            if file["type"] in allowed_types
        }

    async def refresh(self) -> bool:
        """
        Synchronize available assets with branding repository.

        If the current season is not the evergreen, and lacks at least one asset,
        we use the evergreen seasonal dir as fallback for missing assets.

        Finally, if neither the seasonal nor fallback branding directories contain
        an asset, it will simply be ignored.

        Return True if the branding has changed. This will be the case when we enter
        a new season, or when something changes in the current seasons's directory
        in the branding repository.
        """
        old_branding = (self.banner, self.avatar, self.available_icons)
        seasonal_dir = await self._get_files(self.current_season.branding_path, include_dirs=True)

        # Only make a call to the fallback directory if there is something to be gained
        branding_incomplete = any(
            asset not in seasonal_dir
            for asset in (FILE_BANNER, FILE_AVATAR, SERVER_ICONS)
        )
        if branding_incomplete and self.current_season is not SeasonBase:
            fallback_dir = await self._get_files(SeasonBase.branding_path, include_dirs=True)
        else:
            fallback_dir = {}

        # Resolve assets in this directory, None is a safe value
        self.banner = seasonal_dir.get(FILE_BANNER) or fallback_dir.get(FILE_BANNER)
        self.avatar = seasonal_dir.get(FILE_AVATAR) or fallback_dir.get(FILE_AVATAR)

        # Now resolve server icons by making a call to the proper sub-directory
        if SERVER_ICONS in seasonal_dir:
            icons_dir = await self._get_files(f"{self.current_season.branding_path}/{SERVER_ICONS}")
            self.available_icons = list(icons_dir.values())

        elif SERVER_ICONS in fallback_dir:
            icons_dir = await self._get_files(f"{SeasonBase.branding_path}/{SERVER_ICONS}")
            self.available_icons = list(icons_dir.values())

        else:
            self.available_icons = []  # This should never be the case, but an empty list is a safe value

        # GitHubFile instances carry a `sha` attr so this will pick up if a file changes
        branding_changed = old_branding != (self.banner, self.avatar, self.available_icons)

        if branding_changed:
            log.info(f"New branding detected (season: {self.current_season.season_name})")
            await self._reset_remaining_icons()
            await self._reset_days_since_cycle()

        return branding_changed

    async def cycle(self) -> bool:
        """
        Apply the next-up server icon.

        Returns True if an icon is available and successfully gets applied, False otherwise.
        """
        if not self.available_icons:
            log.info("Cannot cycle: no icons for this season")
            return False

        if not self.remaining_icons:
            log.info("Reset & shuffle remaining icons")
            await self._reset_remaining_icons()

        next_up = self.remaining_icons.pop(0)
        success = await self.bot.set_icon(next_up.download_url)

        return success

    async def apply(self) -> t.List[str]:
        """
        Apply current branding to the guild and bot.

        This delegates to the bot instance to do all the work. We only provide download urls
        for available assets. Assets unavailable in the branding repo will be ignored.

        Returns a list of names of all failed assets. An asset is considered failed
        if it isn't found in the branding repo, or if something goes wrong while the
        bot is trying to apply it.

        An empty list denotes that all assets have been applied successfully.
        """
        report = {asset: False for asset in ("banner", "avatar", "nickname", "icon")}

        if self.banner is not None:
            report["banner"] = await self.bot.set_banner(self.banner.download_url)

        if self.avatar is not None:
            report["avatar"] = await self.bot.set_avatar(self.avatar.download_url)

        if self.current_season.bot_name:
            report["nickname"] = await self.bot.set_nickname(self.current_season.bot_name)

        report["icon"] = await self.cycle()

        failed_assets = [asset for asset, succeeded in report.items() if not succeeded]
        return failed_assets

    @with_role(*MODERATION_ROLES)
    @commands.group(name="branding")
    async def branding_cmds(self, ctx: commands.Context) -> None:
        """Manual branding control."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @branding_cmds.command(name="list", aliases=["ls"])
    async def branding_list(self, ctx: commands.Context) -> None:
        """List all available seasons and branding sources."""
        embed = discord.Embed(title="Available seasons", colour=Colours.soft_green)

        for season in get_all_seasons():
            if season is SeasonBase:
                active_when = "always"
            else:
                active_when = f"in {human_months(season.months)}"

            description = (
                f"Active {active_when}\n"
                f"Branding: {season.branding_path}"
            )
            embed.add_field(name=season.season_name, value=description, inline=False)

        await ctx.send(embed=embed)

    @branding_cmds.command(name="set")
    async def branding_set(self, ctx: commands.Context, *, season_name: t.Optional[str] = None) -> None:
        """
        Manually set season, or reset to current if none given.

        Season search is a case-less comparison against both seasonal class name,
        and its `season_name` attr.

        This only pre-loads the cog's internal state to the chosen season, but does not
        automatically apply the branding. As that is an expensive operation, the `apply`
        command must be called explicitly after this command finishes.

        This means that this command can be used to 'preview' a season gathering info
        about its available assets, without applying them to the guild.

        If the daemon is running, it will automatically reset the season to current when
        it wakes up. The season set via this command can therefore remain 'detached' from
        what it should be - the daemon will make sure that it's set back properly.
        """
        if season_name is None:
            new_season = get_current_season()
        else:
            new_season = get_season(season_name)
            if new_season is None:
                raise BrandingError("No such season exists")

        if self.current_season is new_season:
            raise BrandingError(f"Season {self.current_season.season_name} already active")

        self.current_season = new_season
        await self.branding_refresh(ctx)

    @branding_cmds.command(name="info", aliases=["status"])
    async def branding_info(self, ctx: commands.Context) -> None:
        """
        Show available assets for current season.

        This can be used to confirm that assets have been resolved properly.
        When `apply` is used, it attempts to upload exactly the assets listed here.
        """
        await ctx.send(embed=await self._info_embed())

    @branding_cmds.command(name="refresh")
    async def branding_refresh(self, ctx: commands.Context) -> None:
        """Sync currently available assets with branding repository."""
        async with ctx.typing():
            await self.refresh()
            await self.branding_info(ctx)

    @branding_cmds.command(name="apply")
    async def branding_apply(self, ctx: commands.Context) -> None:
        """
        Apply current season's branding to the guild.

        Use `info` to check which assets will be applied. Shows which assets have
        failed to be applied, if any.
        """
        async with ctx.typing():
            failed_assets = await self.apply()
            if failed_assets:
                raise BrandingError(f"Failed to apply following assets: {', '.join(failed_assets)}")

            response = discord.Embed(description=f"All assets applied {Emojis.ok_hand}", colour=Colours.soft_green)
            await ctx.send(embed=response)

    @branding_cmds.command(name="cycle")
    async def branding_cycle(self, ctx: commands.Context) -> None:
        """
        Apply the next-up guild icon, if multiple are available.

        The order is random.
        """
        async with ctx.typing():
            success = await self.cycle()
            if not success:
                raise BrandingError("Failed to cycle icon")

            response = discord.Embed(description=f"Success {Emojis.ok_hand}", colour=Colours.soft_green)
            await ctx.send(embed=response)

    @branding_cmds.group(name="daemon", aliases=["d", "task"])
    async def daemon_group(self, ctx: commands.Context) -> None:
        """Control the background daemon."""
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @daemon_group.command(name="status")
    async def daemon_status(self, ctx: commands.Context) -> None:
        """Check whether daemon is currently active."""
        if self._daemon_running:
            remaining_time = (arrow.utcnow() + time_until_midnight()).humanize()
            response = discord.Embed(description=f"Daemon running {Emojis.ok_hand}", colour=Colours.soft_green)
            response.set_footer(text=f"Next refresh {remaining_time}")
        else:
            response = discord.Embed(description="Daemon not running", colour=Colours.soft_red)

        await ctx.send(embed=response)

    @daemon_group.command(name="start", enabled=False)
    async def daemon_start(self, ctx: commands.Context) -> None:
        """If the daemon isn't running, start it."""
        if self._daemon_running:
            raise BrandingError("Daemon already running!")

        self.daemon = self.bot.loop.create_task(self._daemon_func())
        self._write_config("daemon_active", True)

        response = discord.Embed(description=f"Daemon started {Emojis.ok_hand}", colour=Colours.soft_green)
        await ctx.send(embed=response)

    @daemon_group.command(name="stop", enabled=False)
    async def daemon_stop(self, ctx: commands.Context) -> None:
        """If the daemon is running, stop it."""
        if not self._daemon_running:
            raise BrandingError("Daemon not running!")

        self.daemon.cancel()
        self._write_config("daemon_active", False)

        response = discord.Embed(description=f"Daemon stopped {Emojis.ok_hand}", colour=Colours.soft_green)
        await ctx.send(embed=response)


def setup(bot: SeasonalBot) -> None:
    """Load BrandingManager cog."""
    bot.add_cog(BrandingManager(bot))
