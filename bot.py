import discord
from discord.ext import commands
import asyncio
import threading
import random
import datetime
import io
import os
import tempfile

import pyttsx3
from PIL import Image


# ==============================
# BOT SETUP
# ==============================

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=">", intents=intents)

try:
    tts_engine = pyttsx3.init()
    voices = tts_engine.getProperty("voices")
    if voices:
        for voice in voices:
            if "Daniel" in voice.name:
                tts_engine.setProperty("voice", voice.id)
                break
except Exception:
    tts_engine = None

CHANNEL_ID = 1546703323514535988

terminal_started = False
active_polls = {}
piglock_users = set()
piglock_webhooks = {}
POLL_EMOJIS = [
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣",
    "🔟"
]


# ==============================
# BOT READY
# ==============================

@bot.event
async def on_ready():
    global terminal_started

    print(f"Logged in as {bot.user}")

    if not terminal_started:
        terminal_started = True

        print("==============================")
        print("Terminal mode is ready!")
        print()
        print("MODERATION")
        print("kick <user ID> [reason]")
        print("ban <user ID> [reason]")
        print("unban <user ID>")
        print("timeout <user ID> <minutes> [reason]")
        print("warn <user ID> [reason]")
        print("piglock <user ID>")
        print("purge <amount>")
        print()
        print("FUN")
        print("say <message>")
        print("tts <message>")
        print("join")
        print("leave")
        print("vctts <message>")
        print("ping")
        print("fact")
        print("pp")
        print("poll question | option1 | option2")
        print("coinflip")
        print("choose option1 | option2")
        print("ship <user ID> <user ID>")
        print("rate <user ID>")
        print("simp <user ID>")
        print("roll <number>")
        print("8ball <question>")
        print("mock <message>")
        print("reverse <message>")
        print()
        print("IMAGE")
        print("Reply to a picture with >gif")
        print()
        print("INFO")
        print("userinfo <user ID>")
        print("serverinfo")
        print("avatar <user ID>")
        print()
        print("Type help for this list again.")
        print("==============================")

        threading.Thread(target=terminal, daemon=True).start()


# ==============================
# BASIC COMMANDS
# ==============================

@bot.command()
async def hello(ctx):
    await ctx.reply("Hello!")


@bot.command()
async def ping(ctx):
    await ctx.reply("Pong!")


@bot.command()
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)


@bot.command()
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.reply("❌ Join a voice channel first.")
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client is not None:
        if ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
        await ctx.reply(f"✅ Joined {channel.name}.")
        return

    await channel.connect()
    await ctx.reply(f"✅ Joined {channel.name}.")


@bot.command()
async def leave(ctx):
    if ctx.voice_client is None:
        await ctx.reply("❌ I'm not in a voice channel.")
        return

    await ctx.voice_client.disconnect()
    await ctx.reply("✅ Left the voice channel.")


@bot.command()
async def tts(ctx, *, message):
    await ctx.send(message, tts=True)


@bot.command(name="vctts")
async def vctts_command(ctx, *, message):
    if ctx.author.voice is None:
        await ctx.reply("❌ Join a voice channel first.")
        return

    if ctx.voice_client is None:
        await ctx.author.voice.channel.connect()

    audio_path = create_tts_audio(message)

    if audio_path is None:
        await ctx.reply("❌ TTS is unavailable on this machine.")
        return

    try:
        source = discord.FFmpegPCMAudio(audio_path)
        ctx.voice_client.play(source)
        await ctx.reply("🔊 Speaking in VC...")
    except Exception as error:
        print(f"VC TTS error: {error}")
        await ctx.reply("❌ FFmpeg is required for VC TTS. Install it and add it to PATH.")


@bot.command(name="vts")
async def vts_command(ctx, *, message):
    await vctts_command(ctx, message=message)


@bot.command()
async def fact(ctx):
    facts = [
        "Octopuses have three hearts.",
        "Honey never spoils.",
        "Bananas are berries, but strawberries aren't.",
        "A group of flamingos is called a flamboyance.",
        "There are more possible chess games than atoms in the universe.",
        "Wombat poop is cube-shaped."
    ]

    await ctx.reply(random.choice(facts))


@bot.command()
async def pp(ctx):
    size = random.randint(1, 12)
    await ctx.reply(f"Your pp is **{size} inches**.")


@bot.command()
async def poll(ctx, *, content):
    parts = [part.strip() for part in content.split("|") if part.strip()]

    if len(parts) < 3:
        await ctx.reply(
            "❌ Use: `>poll question | option1 | option2`\n"
            "Optional: `>poll question | option1 | option2 | 5`"
        )
        return

    threshold = 3

    if parts[-1].isdigit():
        threshold = int(parts[-1])
        parts = parts[:-1]

    question = parts[0]
    options = parts[1:]

    if len(options) < 2:
        await ctx.reply(
            "❌ You need at least 2 options."
        )
        return

    if len(options) > len(POLL_EMOJIS):
        await ctx.reply(
            f"❌ Maximum {len(POLL_EMOJIS)} options."
        )
        return

    if threshold < 1:
        await ctx.reply(
            "❌ Vote threshold must be at least 1."
        )
        return

    embed = discord.Embed(
        title="📊 Poll",
        description=question,
        color=discord.Color.gold()
    )

    for index, option in enumerate(options):
        embed.add_field(
            name=f"{POLL_EMOJIS[index]} {option}",
            value="0 votes",
            inline=False
        )

    embed.set_footer(text=f"First option to reach {threshold} votes wins!")

    message = await ctx.send(embed=embed)

    poll_data = {
        "question": question,
        "options": options,
        "threshold": threshold,
        "votes": {emoji: set() for emoji in POLL_EMOJIS[:len(options)]},
        "message_id": message.id,
        "channel_id": ctx.channel.id,
        "guild_id": ctx.guild.id,
        "user_votes": {}
    }

    active_polls[message.id] = poll_data

    for emoji in POLL_EMOJIS[:len(options)]:
        await message.add_reaction(emoji)

    await ctx.reply(
        f"✅ Poll started! First option to reach **{threshold} votes** wins."
    )


@bot.command()
async def botinfo(ctx):
    embed = discord.Embed(
        title="Bot Info",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Name",
        value=str(ctx.bot.user),
        inline=False
    )

    embed.add_field(
        name="Servers",
        value=str(len(ctx.bot.guilds)),
        inline=True
    )

    embed.add_field(
        name="Users",
        value=str(sum(g.member_count for g in ctx.bot.guilds)),
        inline=True
    )

    await ctx.reply(embed=embed)


# ==============================
# GIF COMMAND
# ==============================

@bot.command()
async def gif(ctx):

    # Make sure the command is a reply
    if ctx.message.reference is None:
        await ctx.reply("❌ Reply to a picture with `>gif`.")
        return

    try:

        # Get the message being replied to
        replied_message = await ctx.channel.fetch_message(
            ctx.message.reference.message_id
        )

        # Make sure the replied message has an attachment
        if not replied_message.attachments:
            await ctx.reply(
                "❌ The message you replied to doesn't have a picture."
            )
            return

        attachment = replied_message.attachments[0]

        # Check file type
        filename = attachment.filename.lower()

        image_extensions = (
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        )

        if not filename.endswith(image_extensions):
            await ctx.reply(
                "❌ The picture must be JPG, JPEG, PNG, or WEBP."
            )
            return

        # Download image
        image_data = await attachment.read()

        # Open image
        image = Image.open(
            io.BytesIO(image_data)
        ).convert("RGB")

        # Convert to a ONE-FRAME GIF
        gif_data = io.BytesIO()

        image.save(
            gif_data,
            format="GIF",
            save_all=True
        )

        gif_data.seek(0)

        # Reply to the >gif command
        await ctx.reply(
            "🎬 Converted to GIF!",
            file=discord.File(
                gif_data,
                filename="converted.gif"
            )
        )

        print(
            f"Converted {attachment.filename} to a 1-frame GIF."
        )

    except Exception as error:

        print(f"GIF error: {error}")

        await ctx.reply(
            "❌ I couldn't convert that picture into a GIF."
        )


# ==============================
# PURGE
# ==============================

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):

    if amount < 1:
        await ctx.reply(
            "Enter a number greater than 0."
        )
        return

    if amount > 100:
        await ctx.reply(
            "You can only purge up to 100 messages."
        )
        return

    try:

        deleted = await ctx.channel.purge(
            limit=amount + 1
        )

        message = await ctx.send(
            f"🧹 {ctx.author.mention} deleted "
            f"**{len(deleted) - 1} messages.**"
        )

        await asyncio.sleep(3)

        await message.delete()

    except discord.Forbidden:

        await ctx.reply(
            "❌ I don't have permission to manage messages."
        )


# ==============================
# KICK
# ==============================

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    if member == ctx.author:
        await ctx.reply(
            "❌ You can't kick yourself."
        )
        return

    if member == bot.user:
        await ctx.reply(
            "❌ You can't kick me."
        )
        return

    try:

        await member.kick(reason=reason)

        await ctx.reply(
            f"👢 **{member}** has been kicked.\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:

        await ctx.reply(
            "❌ I don't have permission to kick that user."
        )


# ==============================
# BAN
# ==============================

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    if member == ctx.author:
        await ctx.reply(
            "❌ You can't ban yourself."
        )
        return

    if member == bot.user:
        await ctx.reply(
            "❌ You can't ban me."
        )
        return

    try:

        await member.ban(reason=reason)

        await ctx.reply(
            f"🔨 **{member}** has been banned.\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:

        await ctx.reply(
            "❌ I don't have permission to ban that user."
        )


# ==============================
# UNBAN
# ==============================

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):

    try:

        user = await bot.fetch_user(user_id)

        await ctx.guild.unban(user)

        await ctx.reply(
            f"✅ **{user}** has been unbanned."
        )

    except discord.NotFound:

        await ctx.reply(
            "❌ User is not banned or doesn't exist."
        )

    except discord.Forbidden:

        await ctx.reply(
            "❌ I don't have permission to unban users."
        )


# ==============================
# TIMEOUT
# ==============================

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(
    ctx,
    member: discord.Member,
    minutes: int,
    *,
    reason="No reason provided"
):

    if minutes < 1:
        await ctx.reply(
            "❌ Timeout must be at least 1 minute."
        )
        return

    if minutes > 40320:
        await ctx.reply(
            "❌ Maximum timeout is 28 days."
        )
        return

    if member == ctx.author:
        await ctx.reply(
            "❌ You can't timeout yourself."
        )
        return

    if member == bot.user:
        await ctx.reply(
            "❌ You can't timeout me."
        )
        return

    try:

        await member.timeout(
            datetime.timedelta(minutes=minutes),
            reason=reason
        )

        await ctx.reply(
            f"🔇 **{member}** has been timed out "
            f"for **{minutes} minutes.**\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:

        await ctx.reply(
            "❌ I don't have permission to timeout that user."
        )


# ==============================
# WARN
# ==============================

@bot.command()
@commands.has_permissions(moderate_members=True)
async def warn(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    if member == ctx.author:
        await ctx.reply(
            "❌ You can't warn yourself."
        )
        return

    if member == bot.user:
        await ctx.reply(
            "❌ You can't warn me."
        )
        return

    try:
        await member.send(
            f"⚠️ You have been warned in **{ctx.guild.name}**.\n"
            f"Reason: {reason}"
        )
    except discord.Forbidden:
        pass

    await ctx.reply(
        f"⚠️ **{member}** has been warned.\n"
        f"Reason: {reason}"
    )


# ==============================
# USER INFO
# ==============================

@bot.command()
async def userinfo(
    ctx,
    member: discord.Member = None
):

    if member is None:
        member = ctx.author

    embed = discord.Embed(
        title="User Info"
    )

    embed.add_field(
        name="Username",
        value=str(member),
        inline=False
    )

    embed.add_field(
        name="User ID",
        value=str(member.id),
        inline=False
    )

    embed.add_field(
        name="Joined Server",
        value=member.joined_at.strftime(
            "%B %d, %Y"
        ),
        inline=False
    )

    embed.add_field(
        name="Account Created",
        value=member.created_at.strftime(
            "%B %d, %Y"
        ),
        inline=False
    )

    if member.avatar:
        embed.set_thumbnail(
            url=member.avatar.url
        )

    await ctx.reply(
        embed=embed
    )


# ==============================
# SERVER INFO
# ==============================

@bot.command()
async def serverinfo(ctx):

    guild = ctx.guild

    embed = discord.Embed(
        title="Server Info"
    )

    embed.add_field(
        name="Server Name",
        value=guild.name,
        inline=False
    )

    embed.add_field(
        name="Server ID",
        value=str(guild.id),
        inline=False
    )

    embed.add_field(
        name="Members",
        value=str(guild.member_count),
        inline=True
    )

    embed.add_field(
        name="Channels",
        value=str(len(guild.channels)),
        inline=True
    )

    embed.add_field(
        name="Roles",
        value=str(len(guild.roles)),
        inline=True
    )

    if guild.icon:
        embed.set_thumbnail(
            url=guild.icon.url
        )

    await ctx.reply(
        embed=embed
    )


# ==============================
# AVATAR
# ==============================

@bot.command()
async def avatar(
    ctx,
    member: discord.Member = None
):

    if member is None:
        member = ctx.author

    if member.avatar:

        await ctx.reply(
            member.avatar.url
        )

    else:

        await ctx.reply(
            "This user doesn't have a custom avatar."
        )


# ==============================
# ROLL
# ==============================

@bot.command()
async def roll(
    ctx,
    number: int = 100
):

    if number < 2:

        await ctx.reply(
            "The number must be at least 2."
        )
        return

    if number > 1000000:

        await ctx.reply(
            "Maximum is 1,000,000."
        )
        return

    result = random.randint(
        1,
        number
    )

    await ctx.reply(
        f"🎲 {ctx.author.mention} rolled "
        f"**{result}** out of **{number}!**"
    )


# ==============================
# 8 BALL
# ==============================

@bot.command(name="8ball")
async def eightball(
    ctx,
    *,
    question
):

    responses = [

        "Yes.",
        "No.",
        "Definitely.",
        "Absolutely not.",
        "Probably.",
        "Probably not.",
        "It is certain.",
        "Ask again later.",
        "I don't know.",
        "The signs point to yes.",
        "The signs point to no."

    ]

    answer = random.choice(
        responses
    )

    await ctx.reply(
        f"🎱 {ctx.author.mention} asks:\n"
        f"**{question}**\n\n"
        f"🔮 **{answer}**"
    )


# ==============================
# COINFLIP
# ==============================

@bot.command()
async def coinflip(ctx):

    result = random.choice(
        ["Heads", "Tails"]
    )

    await ctx.reply(
        f"🪙 {ctx.author.mention} got "
        f"**{result}!**"
    )


# ==============================
# CHOOSE
# ==============================

@bot.command()
async def choose(
    ctx,
    *,
    choices
):

    options = [

        option.strip()

        for option in choices.split("|")

        if option.strip()

    ]

    if len(options) < 2:

        await ctx.reply(
            "Give me at least 2 choices "
            "separated by `|`."
        )

        return

    result = random.choice(
        options
    )

    await ctx.reply(
        f"🤔 I choose **{result}**!"
    )


# ==============================
# SHIP
# ==============================

@bot.command()
async def ship(
    ctx,
    member1: discord.Member,
    member2: discord.Member
):

    percentage = random.randint(
        0,
        100
    )

    await ctx.reply(
        f"❤️ **{member1.display_name} + "
        f"{member2.display_name}**\n"
        f"💖 Compatibility: "
        f"**{percentage}%**"
    )


# ==============================
# RATE
# ==============================

@bot.command()
async def rate(
    ctx,
    member: discord.Member = None
):

    if member is None:
        member = ctx.author

    rating = random.randint(
        1,
        10
    )

    await ctx.reply(
        f"⭐ **{member.display_name}** gets "
        f"**{rating}/10!**"
    )


# ==============================
# SIMP
# ==============================

@bot.command()
async def simp(
    ctx,
    member: discord.Member = None
):

    if member is None:
        member = ctx.author

    percentage = random.randint(
        0,
        100
    )

    await ctx.reply(
        f"💘 **{member.display_name}** is "
        f"**{percentage}% simp.**"
    )


# ==============================
# MOCK
# ==============================

@bot.command()
async def mock(
    ctx,
    *,
    message
):

    result = ""

    for character in message:

        if character.isalpha():

            if random.choice(
                [True, False]
            ):

                result += character.upper()

            else:

                result += character.lower()

        else:

            result += character

    await ctx.reply(
        result
    )


# ==============================
# REVERSE
# ==============================

@bot.command()
async def reverse(
    ctx,
    *,
    message
):

    await ctx.reply(
        message[::-1]
    )


# ==============================
# COMMAND ERRORS
# ==============================

async def update_poll_message(message_id):
    poll_data = active_polls.get(message_id)

    if not poll_data:
        return

    channel = bot.get_channel(poll_data["channel_id"])

    if channel is None:
        return

    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        active_polls.pop(message_id, None)
        return

    embed = discord.Embed(
        title="📊 Poll",
        description=poll_data["question"],
        color=discord.Color.gold()
    )

    option_emojis = list(poll_data["votes"].keys())

    for index, option in enumerate(poll_data["options"]):
        emoji = option_emojis[index]
        vote_count = len(poll_data["votes"][emoji])
        embed.add_field(
            name=f"{emoji} {option}",
            value=f"{vote_count} vote{'s' if vote_count != 1 else ''}",
            inline=False
        )

    embed.set_footer(text=f"First option to reach {poll_data['threshold']} votes wins!")

    await message.edit(embed=embed)


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    poll_data = active_polls.get(payload.message_id)

    if not poll_data:
        return

    if payload.channel_id != poll_data["channel_id"]:
        return

    emoji = str(payload.emoji)
    valid_emojis = list(poll_data["votes"].keys())

    if emoji not in valid_emojis:
        return

    user_id = payload.user_id
    previous_vote = poll_data["user_votes"].get(user_id)

    if previous_vote == emoji:
        return

    if previous_vote:
        poll_data["votes"][previous_vote].discard(user_id)

    poll_data["votes"][emoji].add(user_id)
    poll_data["user_votes"][user_id] = emoji

    await update_poll_message(payload.message_id)

    for option_emoji, voters in poll_data["votes"].items():
        option_index = valid_emojis.index(option_emoji)
        if len(voters) >= poll_data["threshold"]:
            winning_option = poll_data["options"][option_index]
            winning_votes = len(voters)

            channel = bot.get_channel(poll_data["channel_id"])

            if channel:
                await channel.send(
                    f"🎉 Poll winner: **{winning_option}** with **{winning_votes} votes**!"
                )

            active_polls.pop(payload.message_id, None)
            return


@bot.event
async def on_raw_reaction_remove(payload):
    poll_data = active_polls.get(payload.message_id)

    if not poll_data:
        return

    if payload.channel_id != poll_data["channel_id"]:
        return

    emoji = str(payload.emoji)
    valid_emojis = list(poll_data["votes"].keys())

    if emoji not in valid_emojis:
        return

    user_id = payload.user_id

    if user_id in poll_data["user_votes"] and poll_data["user_votes"][user_id] == emoji:
        poll_data["votes"][emoji].discard(user_id)
        del poll_data["user_votes"][user_id]

    await update_poll_message(payload.message_id)


@bot.command()
async def piglock(ctx, member: discord.Member = None):
    allowed_users = {
        550232773697470465,
        1438679517156872304
    }

    if ctx.author.id not in allowed_users:
        await ctx.reply("idiot think they jz or vazor lol")
        return

    if member is None:
        await ctx.reply("❌ Use: `>piglock @user`")
        return

    if member.id in piglock_users:
        piglock_users.remove(member.id)
        await ctx.reply(f"❌ Piglock removed from {member.mention}.")
        return

    piglock_users.add(member.id)
    await ctx.reply(f"✅ Piglock enabled for {member.mention}.")


async def get_piglock_webhook(channel):
    if channel.id in piglock_webhooks:
        return piglock_webhooks[channel.id]

    try:
        webhook = await channel.create_webhook(name="Piglock")
    except discord.Forbidden:
        return None

    piglock_webhooks[channel.id] = webhook
    return webhook


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id not in piglock_users:
        await bot.process_commands(message)
        return

    try:
        await message.delete()
    except discord.Forbidden:
        pass

    content = message.content.strip()

    if not content:
        return

    pig_text = f"🐷 {content} 🐷 oink"
    avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url

    webhook = await get_piglock_webhook(message.channel)

    if webhook:
        await webhook.send(
            content=pig_text,
            username=message.author.display_name,
            avatar_url=avatar_url,
            allowed_mentions=discord.AllowedMentions.none()
        )
    else:
        await message.channel.send(
            f"{message.author.display_name}: {pig_text}"
        )

    await bot.process_commands(message)


@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.reply(
            "❌ You don't have permission "
            "to use that command."
        )

    elif isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.reply(
            "❌ You're missing an argument."
        )

    elif isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.reply(
            "❌ Invalid user or argument."
        )

    elif isinstance(
        error,
        commands.CommandNotFound
    ):

        pass

    else:

        print(
            f"Error: {error}"
        )


# ==========================================================
# TERMINAL
# ==========================================================

def terminal():

    while True:

        try:

            command = input(
                "Bot> "
            ).strip()


            # ==============================
            # HELP
            # ==============================

            if command == "help":

                print("==============================")

                print("Terminal commands:")

                print()

                print("MODERATION")

                print(
                    "kick <user ID> [reason]"
                )

                print(
                    "ban <user ID> [reason]"
                )

                print(
                    "unban <user ID>"
                )

                print(
                    "timeout <user ID> <minutes> [reason]"
                )

                print(
                    "warn <user ID> [reason]"
                )

                print(
                    "purge <amount>"
                )

                print()

                print("FUN")

                print(
                    "say <message>"
                )

                print(
                    "tts <message>"
                )

                print(
                    "join"
                )

                print(
                    "leave"
                )

                print(
                    "vctts <message>"
                )

                print(
                    "ping"
                )

                print(
                    "fact"
                )

                print(
                    "pp"
                )

                print(
                    "poll question | option1 | option2"
                )

                print(
                    "coinflip"
                )

                print(
                    "choose option1 | option2"
                )

                print(
                    "ship <user ID> <user ID>"
                )

                print(
                    "rate <user ID>"
                )

                print(
                    "simp <user ID>"
                )

                print(
                    "roll <number>"
                )

                print(
                    "8ball <question>"
                )

                print(
                    "mock <message>"
                )

                print(
                    "reverse <message>"
                )

                print()

                print("IMAGE")

                print(
                    "gif"
                )

                print(
                    "Use >gif in Discord by replying to a picture."
                )

                print()

                print("INFO")

                print(
                    "userinfo <user ID>"
                )

                print(
                    "serverinfo"
                )

                print(
                    "avatar <user ID>"
                )

                print("==============================")


            # ==============================
            # SAY
            # ==============================

            elif command.startswith(
                "say "
            ):

                message = command[4:]

                asyncio.run_coroutine_threadsafe(
                    terminal_send(message),
                    bot.loop
                )


            # ==============================
            # TTS
            # ==============================

            elif command.startswith("tts "):

                message = command[4:]
                speak_text(message)
                print(f"Speaking: {message}")


            # ==============================
            # PING
            # ==============================

            elif command == "ping":

                asyncio.run_coroutine_threadsafe(
                    terminal_send("Pong!"),
                    bot.loop
                )


            # ==============================
            # VOICE COMMANDS
            # ==============================

            elif command == "join":

                print("Use >join in Discord. Voice commands are not supported in terminal mode.")


            elif command == "leave":

                print("Use >leave in Discord. Voice commands are not supported in terminal mode.")


            elif command.startswith("vctts "):

                print("Use >vctts <message> in Discord. Voice commands are not supported in terminal mode.")


            # ==============================
            # FACT
            # ============================== 

            elif command == "fact":

                asyncio.run_coroutine_threadsafe(
                    terminal_fact(),
                    bot.loop
                )


            # ============================== 
            # PP
            # ============================== 

            elif command == "pp":

                asyncio.run_coroutine_threadsafe(
                    terminal_pp(),
                    bot.loop
                )


            # ============================== 
            # PIGLOCK
            # ============================== 

            elif command.startswith("piglock "):

                try:
                    user_id = int(command[8:])
                    asyncio.run_coroutine_threadsafe(
                        terminal_piglock(user_id),
                        bot.loop
                    )
                except ValueError:
                    print("Usage: piglock <user ID>")


            # ============================== 
            # BOTINFO
            # ============================== 

            elif command == "botinfo":

                asyncio.run_coroutine_threadsafe(
                    terminal_botinfo(),
                    bot.loop
                )


            # ============================== 

            elif command.startswith(
                "purge "
            ):

                try:

                    amount = int(
                        command[6:]
                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_purge(amount),
                        bot.loop
                    )

                except ValueError:

                    print(
                        "Usage: purge <amount>"
                    )


            # ==============================
            # KICK
            # ==============================

            elif command.startswith(
                "kick "
            ):

                parts = command.split(
                    " ",
                    2
                )

                try:

                    user_id = int(
                        parts[1]
                    )

                    reason = (

                        parts[2]

                        if len(parts) > 2

                        else "No reason provided"

                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_kick(
                            user_id,
                            reason
                        ),
                        bot.loop
                    )

                except (
                    ValueError,
                    IndexError
                ):

                    print(
                        "Usage: kick <user ID> [reason]"
                    )


            # ==============================
            # BAN
            # ==============================

            elif command.startswith(
                "ban "
            ):

                parts = command.split(
                    " ",
                    2
                )

                try:

                    user_id = int(
                        parts[1]
                    )

                    reason = (

                        parts[2]

                        if len(parts) > 2

                        else "No reason provided"

                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_ban(
                            user_id,
                            reason
                        ),
                        bot.loop
                    )

                except (
                    ValueError,
                    IndexError
                ):

                    print(
                        "Usage: ban <user ID> [reason]"
                    )


            # ==============================
            # UNBAN
            # ==============================

            elif command.startswith(
                "unban "
            ):

                try:

                    user_id = int(
                        command[6:]
                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_unban(user_id),
                        bot.loop
                    )

                except ValueError:

                    print(
                        "Usage: unban <user ID>"
                    )


            # ==============================
            # TIMEOUT
            # ==============================

            elif command.startswith(
                "timeout "
            ):

                parts = command.split(
                    " ",
                    3
                )

                try:

                    user_id = int(
                        parts[1]
                    )

                    minutes = int(
                        parts[2]
                    )

                    reason = (

                        parts[3]

                        if len(parts) > 3

                        else "No reason provided"

                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_timeout(
                            user_id,
                            minutes,
                            reason
                        ),
                        bot.loop
                    )

                except (
                    ValueError,
                    IndexError
                ):

                    print(
                        "Usage: timeout <user ID> <minutes> [reason]"
                    )


            # ==============================
            # WARN
            # ==============================

            elif command.startswith(
                "warn "
            ):

                parts = command.split(
                    " ",
                    2
                )

                try:

                    user_id = int(
                        parts[1]
                    )

                    reason = (

                        parts[2]

                        if len(parts) > 2

                        else "No reason provided"

                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_warn(
                            user_id,
                            reason
                        ),
                        bot.loop
                    )

                except (
                    ValueError,
                    IndexError
                ):

                    print(
                        "Usage: warn <user ID> [reason]"
                    )


            # ==============================
            # COINFLIP
            # ==============================

            elif command == "coinflip":

                asyncio.run_coroutine_threadsafe(
                    terminal_coinflip(),
                    bot.loop
                )


            # ==============================
            # CHOOSE
            # ==============================

            elif command.startswith(
                "choose "
            ):

                choices = command[7:]

                asyncio.run_coroutine_threadsafe(
                    terminal_choose(choices),
                    bot.loop
                )


            # ==============================
            # SHIP
            # ==============================

            elif command.startswith(
                "ship "
            ):

                parts = command.split()

                if len(parts) != 3:

                    print(
                        "Usage: ship <user ID> <user ID>"
                    )

                else:

                    try:

                        user1 = int(
                            parts[1]
                        )

                        user2 = int(
                            parts[2]
                        )

                        asyncio.run_coroutine_threadsafe(
                            terminal_ship(
                                user1,
                                user2
                            ),
                            bot.loop
                        )

                    except ValueError:

                        print(
                            "User IDs must be numbers."
                        )


            # ==============================
            # RATE
            # ==============================

            elif command.startswith(
                "rate "
            ):

                try:

                    user_id = int(
                        command[5:]
                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_rate(user_id),
                        bot.loop
                    )

                except ValueError:

                    print(
                        "Usage: rate <user ID>"
                    )


            # ==============================
            # SIMP
            # ==============================

            elif command.startswith(
                "simp "
            ):

                try:

                    user_id = int(
                        command[5:]
                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_simp(user_id),
                        bot.loop
                    )

                except ValueError:

                    print(
                        "Usage: simp <user ID>"
                    )


            # ==============================
            # ROLL
            # ==============================

            elif command.startswith(
                "roll "
            ):

                try:

                    number = int(
                        command[5:]
                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_roll(number),
                        bot.loop
                    )

                except ValueError:

                    print(
                        "Usage: roll <number>"
                    )


            # ==============================
            # 8BALL
            # ==============================

            elif command.startswith(
                "8ball "
            ):

                question = command[6:]

                asyncio.run_coroutine_threadsafe(
                    terminal_8ball(question),
                    bot.loop
                )


            # ==============================
            # MOCK
            # ==============================

            elif command.startswith(
                "mock "
            ):

                message = command[5:]

                asyncio.run_coroutine_threadsafe(
                    terminal_mock(message),
                    bot.loop
                )


            # ==============================
            # REVERSE
            # ==============================

            elif command.startswith(
                "reverse "
            ):

                message = command[8:]

                asyncio.run_coroutine_threadsafe(
                    terminal_reverse(message),
                    bot.loop
                )


            # ==============================
            # USERINFO
            # ==============================

            elif command.startswith(
                "userinfo "
            ):

                try:

                    user_id = int(
                        command[9:]
                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_userinfo(user_id),
                        bot.loop
                    )

                except ValueError:

                    print(
                        "Usage: userinfo <user ID>"
                    )


            # ==============================
            # SERVERINFO
            # ==============================

            elif command == "serverinfo":

                asyncio.run_coroutine_threadsafe(
                    terminal_serverinfo(),
                    bot.loop
                )


            # ==============================
            # AVATAR
            # ==============================

            elif command.startswith(
                "avatar "
            ):

                try:

                    user_id = int(
                        command[7:]
                    )

                    asyncio.run_coroutine_threadsafe(
                        terminal_avatar(user_id),
                        bot.loop
                    )

                except ValueError:

                    print(
                        "Usage: avatar <user ID>"
                    )


            else:

                print(
                    "Unknown command. Type 'help'."
                )


        except KeyboardInterrupt:

            break


# ==========================================================
# TERMINAL FUNCTIONS
# ==========================================================

def create_tts_audio(message):
    if not message or not message.strip():
        return None

    if tts_engine is None:
        return None

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_file.close()
    temp_path = temp_file.name

    try:
        tts_engine.save_to_file(message, temp_path)
        tts_engine.runAndWait()
        return temp_path
    except Exception as error:
        print(f"TTS file error: {error}")
        try:
            os.remove(temp_path)
        except OSError:
            pass
        return None


def speak_text(message):
    if not message or not message.strip():
        return

    if tts_engine is None:
        print("TTS is unavailable on this system.")
        return

    try:
        tts_engine.say(message)
        tts_engine.runAndWait()
    except Exception as error:
        print(f"TTS error: {error}")


async def get_general_channel():

    channel = bot.get_channel(
        CHANNEL_ID
    )

    if channel is None:

        print(
            "Channel not found. Check CHANNEL_ID."
        )

    return channel


async def terminal_send(message):

    channel = await get_general_channel()

    if channel:

        await channel.send(
            message
        )

        print(
            "Message sent!"
        )


async def terminal_fact():

    facts = [
        "Octopuses have three hearts.",
        "Honey never spoils.",
        "Bananas are berries, but strawberries aren't.",
        "A group of flamingos is called a flamboyance.",
        "There are more possible chess games than atoms in the universe.",
        "Wombat poop is cube-shaped."
    ]

    result = random.choice(facts)

    print(result)

    channel = await get_general_channel()

    if channel:
        await channel.send(result)


async def terminal_piglock(user_id):
    try:
        user = await bot.fetch_user(user_id)
    except discord.NotFound:
        print("User not found.")
        return

    if user.id in piglock_users:
        piglock_users.remove(user.id)
        print(f"Piglock removed from {user}.")
        return

    piglock_users.add(user.id)
    print(f"Piglock enabled for {user}.")


async def terminal_pp():

    size = random.randint(1, 12)
    message = f"Your pp is **{size} inches**."

    print(message)

    channel = await get_general_channel()

    if channel:
        await channel.send(message)


async def terminal_poll(content):

    parts = [part.strip() for part in content.split("|") if part.strip()]

    if len(parts) < 3:
        print("Usage: poll question | option1 | option2")
        return

    question = parts[0]
    options = parts[1:]
    result = random.choice(options)

    message = f"📊 **Poll:** {question}\n🎯 I choose **{result}**!"

    print(message)

    channel = await get_general_channel()

    if channel:
        await channel.send(message)


async def terminal_botinfo():

    print()
    print(f"Bot: {bot.user}")
    print(f"Servers: {len(bot.guilds)}")
    print(f"Users: {sum(g.member_count for g in bot.guilds)}")
    print()

    channel = await get_general_channel()

    if channel:
        await channel.send(
            f"🤖 **Bot Info**\n"
            f"Name: {bot.user}\n"
            f"Servers: {len(bot.guilds)}\n"
            f"Users: {sum(g.member_count for g in bot.guilds)}"
        )


async def terminal_purge(amount):

    channel = await get_general_channel()

    if not channel:
        return

    if amount < 1 or amount > 100:

        print(
            "Amount must be between 1 and 100."
        )

        return

    try:

        deleted = await channel.purge(
            limit=amount
        )

        print(
            f"Deleted {len(deleted)} messages."
        )

    except discord.Forbidden:

        print(
            "Bot doesn't have Manage Messages permission."
        )


async def terminal_kick(
    user_id,
    reason
):

    channel = await get_general_channel()

    if not channel:
        return

    guild = channel.guild

    try:

        member = guild.get_member(
            user_id
        )

        if member is None:

            member = await guild.fetch_member(
                user_id
            )

        await member.kick(
            reason=reason
        )

        print(
            f"Kicked {member}."
        )

        await channel.send(
            f"👢 **{member}** has been kicked.\n"
            f"Reason: {reason}"
        )

    except discord.NotFound:

        print(
            "User is not in the server."
        )

    except discord.Forbidden:

        print(
            "Bot doesn't have permission to kick this user."
        )


async def terminal_ban(
    user_id,
    reason
):

    channel = await get_general_channel()

    if not channel:
        return

    guild = channel.guild

    try:

        member = guild.get_member(
            user_id
        )

        if member is None:

            member = await guild.fetch_member(
                user_id
            )

        await member.ban(
            reason=reason
        )

        print(
            f"Banned {member}."
        )

        await channel.send(
            f"🔨 **{member}** has been banned.\n"
            f"Reason: {reason}"
        )

    except discord.NotFound:

        print(
            "User is not in the server."
        )

    except discord.Forbidden:

        print(
            "Bot doesn't have permission to ban this user."
        )


async def terminal_unban(
    user_id
):

    channel = await get_general_channel()

    if not channel:
        return

    guild = channel.guild

    try:

        user = await bot.fetch_user(
            user_id
        )

        await guild.unban(
            user
        )

        print(
            f"Unbanned {user}."
        )

        await channel.send(
            f"✅ **{user}** has been unbanned."
        )

    except discord.NotFound:

        print(
            "User isn't banned or doesn't exist."
        )

    except discord.Forbidden:

        print(
            "Bot doesn't have permission to unban users."
        )


async def terminal_timeout(
    user_id,
    minutes,
    reason
):

    channel = await get_general_channel()

    if not channel:
        return

    if minutes < 1 or minutes > 40320:

        print(
            "Timeout must be between 1 minute and 28 days."
        )

        return

    guild = channel.guild

    try:

        member = guild.get_member(
            user_id
        )

        if member is None:

            member = await guild.fetch_member(
                user_id
            )

        await member.timeout(
            datetime.timedelta(
                minutes=minutes
            ),
            reason=reason
        )

        print(
            f"Timed out {member}."
        )

        await channel.send(
            f"🔇 **{member}** has been timed out "
            f"for **{minutes} minutes.**\n"
            f"Reason: {reason}"
        )

    except discord.NotFound:

        print(
            "User isn't in the server."
        )

    except discord.Forbidden:

        print(
            "Bot doesn't have permission to timeout this user."
        )


async def terminal_warn(
    user_id,
    reason
):

    channel = await get_general_channel()

    if not channel:
        return

    guild = channel.guild

    try:

        member = guild.get_member(
            user_id
        )

        if member is None:

            member = await guild.fetch_member(
                user_id
            )

        try:
            await member.send(
                f"⚠️ You have been warned in **{guild.name}**.\n"
                f"Reason: {reason}"
            )
        except discord.Forbidden:
            pass

        print(
            f"Warned {member}."
        )

        await channel.send(
            f"⚠️ **{member}** has been warned.\n"
            f"Reason: {reason}"
        )

    except discord.NotFound:

        print(
            "User isn't in the server."
        )

    except discord.Forbidden:

        print(
            "Bot doesn't have permission to warn this user."
        )


async def terminal_coinflip():

    result = random.choice(
        ["Heads", "Tails"]
    )

    message = f"🪙 **{result}!**"

    print(
        message
    )

    channel = await get_general_channel()

    if channel:

        await channel.send(
            message
        )


async def terminal_choose(
    choices
):

    options = [

        option.strip()

        for option in choices.split("|")

        if option.strip()

    ]

    if len(options) < 2:

        print(
            "Give at least 2 choices separated by |."
        )

        return

    result = random.choice(
        options
    )

    message = f"🤔 I choose **{result}**!"

    print(
        message
    )

    channel = await get_general_channel()

    if channel:

        await channel.send(
            message
        )


async def terminal_ship(
    user1_id,
    user2_id
):

    try:

        user1 = await bot.fetch_user(
            user1_id
        )

        user2 = await bot.fetch_user(
            user2_id
        )

        percentage = random.randint(
            0,
            100
        )

        message = (

            f"❤️ **{user1.display_name} + "
            f"{user2.display_name}**\n"

            f"💖 Compatibility: "
            f"**{percentage}%**"

        )

        print(
            message
        )

        channel = await get_general_channel()

        if channel:

            await channel.send(
                message
            )

    except discord.NotFound:

        print(
            "One or both users couldn't be found."
        )


async def terminal_rate(
    user_id
):

    try:

        user = await bot.fetch_user(
            user_id
        )

        rating = random.randint(
            1,
            10
        )

        message = (

            f"⭐ **{user.display_name}** gets "
            f"**{rating}/10!**"

        )

        print(
            message
        )

        channel = await get_general_channel()

        if channel:

            await channel.send(
                message
            )

    except discord.NotFound:

        print(
            "User not found."
        )


async def terminal_simp(
    user_id
):

    try:

        user = await bot.fetch_user(
            user_id
        )

        percentage = random.randint(
            0,
            100
        )

        message = (

            f"💘 **{user.display_name}** is "
            f"**{percentage}% simp.**"

        )

        print(
            message
        )

        channel = await get_general_channel()

        if channel:

            await channel.send(
                message
            )

    except discord.NotFound:

        print(
            "User not found."
        )


async def terminal_roll(
    number
):

    if number < 2:

        print(
            "Number must be at least 2."
        )

        return

    if number > 1000000:

        print(
            "Maximum is 1,000,000."
        )

        return

    result = random.randint(
        1,
        number
    )

    message = (

        f"🎲 You rolled **{result}** "
        f"out of **{number}!**"

    )

    print(
        message
    )

    channel = await get_general_channel()

    if channel:

        await channel.send(
            message
        )


async def terminal_8ball(
    question
):

    responses = [

        "Yes.",
        "No.",
        "Definitely.",
        "Absolutely not.",
        "Probably.",
        "Probably not.",
        "It is certain.",
        "Ask again later.",
        "I don't know.",
        "The signs point to yes.",
        "The signs point to no."

    ]

    answer = random.choice(
        responses
    )

    message = f"🎱 **{answer}**"

    print(
        message
    )

    channel = await get_general_channel()

    if channel:

        await channel.send(
            message
        )


async def terminal_mock(
    message
):

    result = ""

    for character in message:

        if character.isalpha():

            if random.choice(
                [True, False]
            ):

                result += character.upper()

            else:

                result += character.lower()

        else:

            result += character

    print(
        result
    )

    channel = await get_general_channel()

    if channel:

        await channel.send(
            result
        )


async def terminal_reverse(
    message
):

    result = message[::-1]

    print(
        result
    )

    channel = await get_general_channel()

    if channel:

        await channel.send(
            result
        )


async def terminal_userinfo(
    user_id
):

    try:

        user = await bot.fetch_user(
            user_id
        )

        print()

        print(
            f"Username: {user}"
        )

        print(
            f"User ID: {user.id}"
        )

        print(
            f"Account Created: {user.created_at}"
        )

        print()

    except discord.NotFound:

        print(
            "User not found."
        )


async def terminal_serverinfo():

    channel = await get_general_channel()

    if not channel:
        return

    guild = channel.guild

    print()

    print(
        f"Server: {guild.name}"
    )

    print(
        f"Server ID: {guild.id}"
    )

    print(
        f"Members: {guild.member_count}"
    )

    print(
        f"Channels: {len(guild.channels)}"
    )

    print(
        f"Roles: {len(guild.roles)}"
    )

    print()


async def terminal_avatar(
    user_id
):

    try:

        user = await bot.fetch_user(
            user_id
        )

        if user.avatar:

            print(
                user.avatar.url
            )

        else:

            print(
                "This user doesn't have a custom avatar."
            )

    except discord.NotFound:

        print(
            "User not found."
        )


# ==============================
# START BOT
# ==============================

token = input("Enter your Discord bot token: ").strip()
bot.run(token)