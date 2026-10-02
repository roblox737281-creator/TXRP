import logging
import json
import os
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("moderation-bot")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.sqlite3")


class Database:
    async def initialize(self):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS infractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    member_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS welcome_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL
                )"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS moderation_channels (
                    guild_id INTEGER PRIMARY KEY,
                    infraction_channel_id INTEGER,
                    promotion_channel_id INTEGER
                )"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS infraction_embeds (
                    guild_id INTEGER PRIMARY KEY,
                    embed_json TEXT NOT NULL
                )"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS promotion_embeds (
                    guild_id INTEGER PRIMARY KEY,
                    embed_json TEXT NOT NULL
                )"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS promotion_images (
                    guild_id INTEGER PRIMARY KEY,
                    image_data BLOB NOT NULL
                )"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS admin_roles (
                    guild_id INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL
                )"""
            )
            await db.commit()

    async def add_infraction(self, guild_id: int, member_id: int, moderator_id: int, reason: str) -> int:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO infractions (guild_id, member_id, moderator_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (guild_id, member_id, moderator_id, reason, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_infractions(self, guild_id: int, member_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT id, moderator_id, reason, created_at FROM infractions WHERE guild_id = ? AND member_id = ? ORDER BY id DESC LIMIT 10",
                (guild_id, member_id),
            )
            return await cursor.fetchall()

    async def clear_infractions(self, guild_id: int, member_id: int) -> int:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM infractions WHERE guild_id = ? AND member_id = ?",
                (guild_id, member_id),
            )
            await db.commit()
            return cursor.rowcount

    async def set_welcome_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO welcome_channels (guild_id, channel_id) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id",
                (guild_id, channel_id),
            )
            await db.commit()

    async def get_welcome_channel(self, guild_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT channel_id FROM welcome_channels WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_moderation_channel(self, guild_id: int, channel_type: str, channel_id: int):
        column = "infraction_channel_id" if channel_type == "infraction" else "promotion_channel_id"
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                f"INSERT INTO moderation_channels (guild_id, {column}) VALUES (?, ?) "
                f"ON CONFLICT(guild_id) DO UPDATE SET {column} = excluded.{column}",
                (guild_id, channel_id),
            )
            await db.commit()

    async def get_moderation_channel(self, guild_id: int, channel_type: str):
        column = "infraction_channel_id" if channel_type == "infraction" else "promotion_channel_id"
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                f"SELECT {column} FROM moderation_channels WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_infraction_embed(self, guild_id: int, embed_json: str | None):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            if embed_json is None:
                await db.execute("DELETE FROM infraction_embeds WHERE guild_id = ?", (guild_id,))
            else:
                await db.execute(
                    "INSERT INTO infraction_embeds (guild_id, embed_json) VALUES (?, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET embed_json = excluded.embed_json",
                    (guild_id, embed_json),
                )
            await db.commit()

    async def get_infraction_embed(self, guild_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT embed_json FROM infraction_embeds WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_promotion_embed(self, guild_id: int, embed_json: str | None):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            if embed_json is None:
                await db.execute("DELETE FROM promotion_embeds WHERE guild_id = ?", (guild_id,))
            else:
                await db.execute(
                    "INSERT INTO promotion_embeds (guild_id, embed_json) VALUES (?, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET embed_json = excluded.embed_json",
                    (guild_id, embed_json),
                )
            await db.commit()

    async def get_promotion_embed(self, guild_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT embed_json FROM promotion_embeds WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_promotion_image(self, guild_id: int, image_data: bytes | None):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            if image_data is None:
                await db.execute("DELETE FROM promotion_images WHERE guild_id = ?", (guild_id,))
            else:
                await db.execute(
                    "INSERT INTO promotion_images (guild_id, image_data) VALUES (?, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET image_data = excluded.image_data",
                    (guild_id, image_data),
                )
            await db.commit()

    async def get_promotion_image(self, guild_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT image_data FROM promotion_images WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_admin_role(self, guild_id: int, role_id: int | None):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            if role_id is None:
                await db.execute("DELETE FROM admin_roles WHERE guild_id = ?", (guild_id,))
            else:
                await db.execute(
                    "INSERT INTO admin_roles (guild_id, role_id) VALUES (?, ?) "
                    "ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id",
                    (guild_id, role_id),
                )
            await db.commit()

    async def get_admin_role(self, guild_id: int):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT role_id FROM admin_roles WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None


database = Database()
intents = discord.Intents.default()
intents.members = True


class ModerationBot(commands.Bot):
    async def setup_hook(self):
        await database.initialize()
        await self.tree.sync()
        logger.info("Application commands synced")


bot = ModerationBot(command_prefix="!", intents=intents)


def has_permission_or_admin_role(permission: str):
    async def predicate(interaction: discord.Interaction):
        if interaction.guild_id is None or not isinstance(interaction.user, discord.Member):
            return False
        member = interaction.user
        if member.guild_permissions.administrator or getattr(member.guild_permissions, permission):
            return True
        role_id = await database.get_admin_role(interaction.guild_id)
        return role_id is not None and any(role.id == role_id for role in member.roles)

    return app_commands.check(predicate)


def replace_embed_placeholders(value, placeholders: dict[str, str]):
    if isinstance(value, str):
        for name, replacement in placeholders.items():
            value = value.replace("{" + name + "}", replacement)
        return value
    if isinstance(value, list):
        return [replace_embed_placeholders(item, placeholders) for item in value]
    if isinstance(value, dict):
        return {key: replace_embed_placeholders(item, placeholders) for key, item in value.items()}
    return value


def make_custom_embed(embed_json: str | None, placeholders: dict[str, str], default_embed: discord.Embed):
    if embed_json is None:
        return default_embed
    try:
        embed_data = replace_embed_placeholders(json.loads(embed_json), placeholders)
        return discord.Embed.from_dict(embed_data)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        logger.exception("Could not render custom moderation embed")
        return default_embed


@bot.event
async def on_ready():
    logger.info("Ready as %s (ID: %s)", bot.user, bot.user.id if bot.user else "unknown")


@bot.event
async def on_member_join(member: discord.Member):
    channel_id = await database.get_welcome_channel(member.guild.id)
    if channel_id is None:
        return

    channel = member.guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    embed = discord.Embed(
        title=f"Welcome to {member.guild.name}!",
        description=f"We're glad you're here, {member.mention}.",
        color=discord.Color.green(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    try:
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
    except discord.Forbidden:
        logger.warning("Missing permission to send welcome message in guild %s", member.guild.id)


@bot.tree.command(name="infract", description="Record a warning infraction for a member")
@app_commands.guild_only()
@has_permission_or_admin_role("moderate_members")
@app_commands.checks.cooldown(1, 5)
async def infract(interaction: discord.Interaction, member: discord.Member, reason: str):
    if member.bot:
        await interaction.response.send_message("You can't issue an infraction to a bot.", ephemeral=True)
        return
    if member == interaction.user:
        await interaction.response.send_message("You can't issue an infraction to yourself.", ephemeral=True)
        return

    infraction_id = await database.add_infraction(
        interaction.guild_id,
        member.id,
        interaction.user.id,
        reason,
    )
    await interaction.response.send_message(
        f"Infraction **#{infraction_id}** recorded for {member.mention}. Reason: {reason}",
        allowed_mentions=discord.AllowedMentions.none(),
    )
    channel_id = await database.get_moderation_channel(interaction.guild_id, "infraction")
    channel = interaction.guild.get_channel(channel_id) if channel_id else None
    if isinstance(channel, discord.TextChannel):
        default_embed = discord.Embed(title=f"Infraction #{infraction_id}", color=discord.Color.orange())
        default_embed.add_field(name="Member", value=f"{member.mention} (`{member.id}`)", inline=False)
        default_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        default_embed.add_field(name="Reason", value=reason, inline=False)
        embed_json = await database.get_infraction_embed(interaction.guild_id)
        embed = make_custom_embed(
            embed_json,
            {
                "member": member.mention,
                "member_id": str(member.id),
                "moderator": interaction.user.mention,
                "moderator_id": str(interaction.user.id),
                "reason": reason,
                "infraction_id": str(infraction_id),
                "count": "",
            },
            default_embed,
        )
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            logger.warning("Missing permission to send infraction log in guild %s", interaction.guild_id)
    try:
        await member.send(f"You received a warning in **{interaction.guild.name}**. Reason: {reason}")
    except discord.Forbidden:
        pass


@bot.tree.command(name="infractions", description="View a member's latest warning infractions")
@app_commands.guild_only()
@has_permission_or_admin_role("moderate_members")
async def infractions(interaction: discord.Interaction, member: discord.Member):
    records = await database.get_infractions(interaction.guild_id, member.id)
    if not records:
        await interaction.response.send_message(f"{member.display_name} has no recorded infractions.", ephemeral=True)
        return

    lines = []
    for infraction_id, moderator_id, reason, created_at in records:
        timestamp = int(datetime.fromisoformat(created_at).timestamp())
        lines.append(f"**#{infraction_id}** — <t:{timestamp}:d> by <@{moderator_id}>: {reason}")

    embed = discord.Embed(
        title=f"Infractions for {member.display_name}",
        description="\n".join(lines),
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="clearinfractions", description="Clear all recorded infractions for a member")
@app_commands.guild_only()
@has_permission_or_admin_role("moderate_members")
async def clearinfractions(interaction: discord.Interaction, member: discord.Member):
    count = await database.clear_infractions(interaction.guild_id, member.id)
    await interaction.response.send_message(
        f"Cleared {count} infraction(s) for {member.mention}.",
        ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none(),
    )
    channel_id = await database.get_moderation_channel(interaction.guild_id, "infraction")
    channel = interaction.guild.get_channel(channel_id) if channel_id else None
    if isinstance(channel, discord.TextChannel):
        default_embed = discord.Embed(title="Infractions cleared", color=discord.Color.orange())
        default_embed.add_field(name="Member", value=f"{member.mention} (`{member.id}`)", inline=False)
        default_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        default_embed.add_field(name="Count", value=str(count), inline=True)
        embed_json = await database.get_infraction_embed(interaction.guild_id)
        embed = make_custom_embed(
            embed_json,
            {
                "member": member.mention,
                "member_id": str(member.id),
                "moderator": interaction.user.mention,
                "moderator_id": str(interaction.user.id),
                "reason": "",
                "infraction_id": "",
                "count": str(count),
            },
            default_embed,
        )
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            logger.warning("Missing permission to send infraction log in guild %s", interaction.guild_id)


@bot.tree.command(name="promote", description="Give a member a role")
@app_commands.guild_only()
@has_permission_or_admin_role("manage_roles")
@app_commands.checks.cooldown(1, 5)
async def promote(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    guild = interaction.guild
    actor = interaction.user
    bot_member = guild.me

    if role.is_default() or role.managed:
        await interaction.response.send_message("That role can't be assigned manually.", ephemeral=True)
        return
    if role >= bot_member.top_role:
        await interaction.response.send_message("I can't assign a role equal to or above my highest role.", ephemeral=True)
        return
    if actor != guild.owner and member.top_role >= actor.top_role:
        await interaction.response.send_message("You can only promote members below your highest role.", ephemeral=True)
        return
    if role in member.roles:
        await interaction.response.send_message(f"{member.display_name} already has {role.mention}.", ephemeral=True)
        return

    try:
        await member.add_roles(role, reason=f"Promoted by {actor} ({actor.id})")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to assign that role.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"Promoted {member.mention} by assigning {role.mention}.",
        allowed_mentions=discord.AllowedMentions.none(),
    )
    channel_id = await database.get_moderation_channel(interaction.guild_id, "promotion")
    channel = guild.get_channel(channel_id) if channel_id else None
    if isinstance(channel, discord.TextChannel):
        default_embed = discord.Embed(title="Member promoted", color=discord.Color.green())
        default_embed.add_field(name="Member", value=f"{member.mention} (`{member.id}`)", inline=False)
        default_embed.add_field(name="Role assigned", value=role.mention, inline=True)
        default_embed.add_field(name="Moderator", value=actor.mention, inline=True)
        image_data = await database.get_promotion_image(interaction.guild_id)
        if image_data:
            default_embed.set_image(url="attachment://promotion.jpg")
        try:
            if image_data:
                await channel.send(
                    embed=default_embed,
                    file=discord.File(BytesIO(image_data), filename="promotion.jpg"),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            else:
                await channel.send(embed=default_embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            logger.warning("Missing permission to send promotion log in guild %s", guild.id)


@bot.tree.command(name="setwelcome", description="Choose the channel for new-member welcome messages")
@app_commands.guild_only()
@has_permission_or_admin_role("manage_guild")
async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
    await database.set_welcome_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(
        f"Welcome messages will be sent in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="setadminrole", description="Set or remove the role allowed to use bot admin commands")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
async def setadminrole(interaction: discord.Interaction, role: discord.Role | None = None):
    await database.set_admin_role(interaction.guild_id, role.id if role else None)
    message = f"{role.mention} can now use the bot's moderation and setup commands." if role else "The bot admin role was removed."
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="setinfractionchannel", description="Choose where infraction logs are posted")
@app_commands.guild_only()
@has_permission_or_admin_role("manage_guild")
async def setinfractionchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    await database.set_moderation_channel(interaction.guild_id, "infraction", channel.id)
    await interaction.response.send_message(
        f"Infraction logs will be posted in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="setinfractionembed", description="Set or reset the custom infraction log embed")
@app_commands.guild_only()
@has_permission_or_admin_role("manage_guild")
async def setinfractionembed(interaction: discord.Interaction, embed_json: str | None = None):
    if embed_json is None:
        await database.set_infraction_embed(interaction.guild_id, None)
        await interaction.response.send_message("Infraction logs will use the default embed again.", ephemeral=True)
        return

    if len(embed_json) > 4000:
        await interaction.response.send_message("Embed JSON must be 4000 characters or fewer.", ephemeral=True)
        return

    try:
        embed_data = json.loads(embed_json)
        if isinstance(embed_data, dict) and "embeds" in embed_data:
            embeds = embed_data["embeds"]
            if not isinstance(embeds, list) or not embeds:
                raise ValueError("The embeds array is empty.")
            embed_data = embeds[0]
        if not isinstance(embed_data, dict):
            raise ValueError("Embed JSON must be an embed object or contain an embeds array.")
        embed = discord.Embed.from_dict(embed_data)
        if not any((embed.title, embed.description, embed.fields, embed.image, embed.thumbnail, embed.author, embed.footer)):
            raise ValueError("The embed has no visible content.")
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        await interaction.response.send_message(
            "That doesn't look like valid embed JSON. Paste an embed object or a Discord message JSON object containing an `embeds` array.",
            ephemeral=True,
        )
        return

    await database.set_infraction_embed(interaction.guild_id, json.dumps(embed_data))
    await interaction.response.send_message(
        "Custom infraction embed saved. Placeholders: `{member}`, `{member_id}`, `{moderator}`, `{moderator_id}`, `{reason}`, `{infraction_id}`, `{count}`. Omit the JSON next time to restore the default.",
        ephemeral=True,
    )


@bot.tree.command(name="setpromotionembed", description="Upload a JPG for promotion logs, or reset to the default")
@app_commands.guild_only()
@has_permission_or_admin_role("manage_guild")
async def setpromotionembed(interaction: discord.Interaction, image: discord.Attachment | None = None):
    if image is None:
        await database.set_promotion_image(interaction.guild_id, None)
        await interaction.response.send_message("Promotion logs will use the default embed without an image.", ephemeral=True)
        return

    if image.size > 8 * 1024 * 1024:
        await interaction.response.send_message("The JPG must be 8 MB or smaller.", ephemeral=True)
        return

    if not image.filename.lower().endswith((".jpg", ".jpeg")):
        await interaction.response.send_message(
            "Upload a JPG or JPEG image.",
            ephemeral=True,
        )
        return

    image_data = await image.read()
    if not image_data.startswith(b"\xff\xd8\xff"):
        await interaction.response.send_message("That file doesn't appear to be a valid JPG image.", ephemeral=True)
        return

    await database.set_promotion_image(interaction.guild_id, image_data)
    await interaction.response.send_message(
        "Promotion JPG saved. It will appear on promotion logs; omit the image next time to remove it.",
        ephemeral=True,
    )


@bot.tree.command(name="setpromotionchannel", description="Choose where promotion logs are posted")
@app_commands.guild_only()
@has_permission_or_admin_role("manage_guild")
async def setpromotionchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    await database.set_moderation_channel(interaction.guild_id, "promotion", channel.id)
    await interaction.response.send_message(
        f"Promotion logs will be posted in {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="help", description="Show this bot's moderation and welcome commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Bot commands", color=discord.Color.blurple())
    embed.add_field(name="/infract member reason", value="Record a warning for a member.", inline=False)
    embed.add_field(name="/infractions member", value="View the member's latest 10 warnings.", inline=False)
    embed.add_field(name="/clearinfractions member", value="Clear the member's warning history.", inline=False)
    embed.add_field(name="/promote member role", value="Assign a role to a member.", inline=False)
    embed.add_field(name="/setwelcome channel", value="Set where welcome messages are posted.", inline=False)
    embed.add_field(name="/setadminrole role", value="Allow a role to use bot moderation and setup commands; omit the role to remove it. Requires Manage Server.", inline=False)
    embed.add_field(name="/setinfractionchannel channel", value="Set where infraction logs are posted.", inline=False)
    embed.add_field(name="/setinfractionembed embed_json", value="Set a custom infraction log embed with JSON, or omit it to restore the default.", inline=False)
    embed.add_field(name="/setpromotionchannel channel", value="Set where promotion logs are posted.", inline=False)
    embed.add_field(name="/setpromotionembed image", value="Upload a JPG to show on promotion logs, or omit it to remove the image.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        message = f"Please wait {error.retry_after:.1f} seconds before using that command again."
    elif isinstance(error, app_commands.MissingPermissions):
        message = "You don't have permission to use that command."
    elif isinstance(error, app_commands.NoPrivateMessage):
        message = "This command can only be used in a server."
    else:
        logger.error("Application command failed", exc_info=(type(error), error, error.__traceback__))
        message = "The command failed. Check the bot logs for details."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is missing. Add it to your .env file.")

bot.run(token)