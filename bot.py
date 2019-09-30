import discord
import sys
import sqlite3
import typing
import asyncio
import datetime
import requests
import os
import math
import random
import re
import youtube_dl
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from urllib import parse
from discord.ext import commands

TOKEN = 'NjEyNzE4MjU1NjM4ODM5MzA4.XVmccQ.nBZB73prpOvrIab84VMjGj0BFes' # Not a real token. Demonstration purposes only.
bot = commands.Bot(command_prefix='$')

@bot.event
async def on_ready():
    print("Logged on as {.user}!".format(bot))
    print("Running version {}".format(sys.version))
    await statusChanger()

@bot.event
async def on_member_join(member):
    # Check if the member was muted and reapply it, just in case someone is trying to avoid a mute by rejoining the server
    conn = sqlite3.connect('fhbot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT memberid FROM mutes WHERE memberid=?', (member.id,))
    fetched = cursor.fetchone()
    if fetched != None:
        muted_role = await createMuteRole(member.guild)
        await member.add_roles(muted_role)
    conn.close()

    # CREATE THE WELCOMING BANNER
    # name of the banner image with file extension
    banner_name = "banner.jpg"
    # open the banner file and resize it to 1000x300 px, save the height to variable
    im1 = Image.open("images/{}".format(banner_name)).resize((1000, 300))
    im1_h = im1.height
    # get the url of the joining member's avatar and resize it to 250x250 px, saving the height to variable again
    url = member.avatar_url
    response = requests.get(url)
    im2 = Image.open(BytesIO(response.content)).resize((250, 250))
    im2_h = im2.height
    # draw a mask image with black background and white circle in the middle
    mask = Image.new("L", im2.size, 0)
    maskdraw = ImageDraw.Draw(mask)
    maskdraw.ellipse((0, 0, mask.width, mask.height), fill=255)
    # save the offset to variable, 20 px off the left side and centered vertically
    offset = (20, int((im1_h - im2_h) / 2))
    # paste the avatar with the circle mask applied on top of the banner using the offset above
    im1.paste(im2, offset, mask)
    draw = ImageDraw.Draw(im1)
    # determine the font and its size to use in the welcoming text
    font_name = "arial.ttf"
    font_size = 48
    font = ImageFont.truetype("fonts/{}".format(font_name), font_size)
    # determine the welcoming text to use and draw it on top of the banner, 300px from the left and centered by the height of the text and amount of lines, lambda function to get the ordinal number
    ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(math.floor(n/10)%10!=1)*(n%10<4)*n%10::4])
    member_ordinal = ordinal(member.guild.member_count)
    welcome_text = "Please congratulate\n{.name}\nfor being our {} member!".format(member, member_ordinal)
    text_w, text_h = font.getsize(welcome_text)
    draw.text((300, int((im1_h - text_h) / len(welcome_text.split("\n")))), welcome_text, font=font, fill=(20,20,20,255))
    # save the created file as an image file and send it to the determined channel
    im1.save("images/{.id}_welcome.png".format(member))
    imagefile = discord.File("images/{.id}_welcome.png".format(member))
    await member.guild.get_channel(383107941173166085).send(file=imagefile)
    # remove the image once it's no longer useful to conserve memory
    os.remove("images/{.id}_welcome.png".format(member))

@bot.event
async def on_member_update(before, after):
    roles_before = before.roles
    roles_after = after.roles

# MODERATOR ONLY COMMANDS
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, members: commands.Greedy[discord.Member], *reason: str):
    # Command still unfinished
    kicked_list = ", ".join(member.name for member in members)
    full_reason = " ".join(word for word in reason)
    await ctx.send("{} not kicked because the command is not ready yet but the reason was {}".format(kicked_list, full_reason))

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: typing.Union[discord.User, int], days: typing.Optional[int] = 0, *, reason: typing.Optional[str]):
    # Initialise the member ID just in case
    memberid = 0
    # Check if the user entered an ID or tagged a member
    if type(member) is int:
        memberid = member
    else:
        memberid = member.id
    # The bot can't remove more messages than past 7 days, so change any number greater than 7 to 7
    if days > 7:
        days = 7
    # Ban the member and delete the specified amount of messages (default 0), also inform about the action
    await ctx.message.guild.ban(discord.Object(id=memberid), reason=reason, delete_message_days=days)
    await ctx.send("<@{}> was banned.".format(memberid))
    print("{.author} banned {} with reason: {}".format(ctx, member, reason))
@ban.error
async def ban_error(ctx, error):
    # Catch any errors if the user enters an invalid name or ID
    if isinstance(error, discord.ext.commands.BadUnionArgument):
        await ctx.send("Member not found.")
    elif isinstance(error, discord.ext.commands.errors.CommandInvokeError):
        await ctx.send("User not found.")
    else:
        print("{.author} attempted to run the command 'ban' and was met with {}: {}".format(ctx, type(error), error))

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, memberid: int, *, reason: typing.Optional[str]):
    # Unban the member and inform about it
    await ctx.guild.unban(discord.Object(id=memberid), reason=reason)
    await ctx.send("<@{}> was unbanned.".format(memberid))
    print("{.author} unbanned {} with reason: {}".format(ctx, memberid, reason))

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason):
    # Check if the user tagged a proper member
    try:
        warnedid = member.id
    except:
        ctx.send("Member not found.")
    # Connect to the Sqlite database and save the warning there
    conn = sqlite3.connect('fhbot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO warnings (memberid, reason, issuerid) VALUES (?, ?, ?)', (warnedid, reason, ctx.message.author.id,))
    conn.commit()
    conn.close()
    # Inform about the warning and send a message to the user who was warned
    print("{.author} warned {} for: {}".format(ctx, member, reason))
    await ctx.send("{.mention} was warned.".format(member))
    await member.send("You were warned for: {}".format(reason))
@warn.error
async def warn_error(ctx, error):
    # Check that the user actually includes a reason
    if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
        await ctx.send("Please include a reason for logging purposes.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def removewarn(ctx, arg):
    # initalise the ID of the warning, just in case
    warnid = 0
    # check that the user enters an integer
    try:
        warnid = int(arg)
    except ValueError:
        await ctx.send('{} is not a valid ID.'.format(arg))
        return
    # connect to database and check if a warning with selected ID is found
    conn = sqlite3.connect('fhbot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT memberid, reason FROM warnings WHERE warningid=?', (warnid,))
    fetched = cursor.fetchone()
    # if no warning is found, inform the user and end the function
    if fetched == None:
        await ctx.send("No warnings with ID {} found.".format(warnid))
        conn.close()
        return
    # in case of a typo, confirm that the warning is the correct one and ask the user to add a reaction accordingly
    bot_message = await ctx.send('Are you sure you want to remove "{}" from <@{}>?'.format(fetched[1], fetched[0]))
    await bot_message.add_reaction("✅")
    await bot_message.add_reaction("❌")

    # check that the user who reacts is the user who initialised the command, and that they react with the correct reaction
    def check_approve(reaction, user):
        return user == ctx.author and (reaction.emoji == "✅" or reaction.emoji == "❌")
    
    # use the above check to proceed and do nothing if no reaction is given in 60 seconds
    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check_approve)
    except asyncio.TimeoutError:
        await bot_message.delete()
    else:
        # if approved, inform that the warning was deleted and proceed to remove it from the database, otherwise do nothing
        if reaction.emoji == "✅":
            print('{.author} removed warning "{}" from {}'.format(ctx, fetched[1], fetched[0]))
            await bot_message.edit(content='Warning "{}" removed from <@{}>'.format(fetched[1], fetched[0]))
            await bot_message.clear_reactions()
            cursor.execute('DELETE FROM warnings WHERE warningid=?', (warnid,))
            conn.commit()
        elif reaction.emoji == "❌":
            await bot_message.delete()
    conn.close()

@bot.command()
@commands.has_permissions(kick_members=True)
async def warnings(ctx, member: discord.Member):
    # Check if the user tagged a proper member
    try:
        memberid = member.id
    except:
        await ctx.send("Member not found.")
        return
    # Connect to the database and get the warnings of the specified user
    conn = sqlite3.connect('fhbot.db')
    cursor = conn.cursor()
    title = "Warnings of {.display_name}".format(member)
    # Collect the warnings into an embed and show the warning's ID, issuer and the reason
    description = ""
    for row in cursor.execute('SELECT warningid, reason, issuerid FROM warnings WHERE memberid=?', (memberid,)):
        description += "\n"
        description += "ID: {} Issuer: <@{}> Reason: {}".format(row[0], row[2], row[1])
    embed = discord.Embed(title=title, description=description, color=0xff0000)
    await ctx.send(embed=embed)
    conn.close()

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *time: str):
    muted_role = await createMuteRole(ctx.guild)
    # Add the created role to the muted member
    await member.add_roles(muted_role)
    # If time was specified, go for the timed unmute
    if len(time) > 0:
        print("Time was specified and it was {}".format(time))
        # The smallest specifiable unit is minutes
        minutes = 0
        # Convert each unit to minutes and check that the time does not exceed 7 days
        for timeunit in time:
            if "d" in timeunit:
                days = int(timeunit.split("d")[0])
                if days > 7:
                    await ctx.send("Time cannot exceed 7 days.")
                    return
                minutes += days * 1440
            elif "h" in timeunit:
                hours = int(timeunit.split("h")[0])
                if hours > 168:
                    await ctx.send("Time cannot exceed 7 days.")
                    return
                minutes += hours * 60
            elif "m" in timeunit:
                tempmin = int(timeunit.split("m")[0])
                if tempmin > 10080:
                    await ctx.send("Time cannot exceed 7 days.")
                    return
                minutes += tempmin
            else:
                await ctx.send("Unknown or missing time unit.")
                return
            # Check after every round that time has not exceeded 7 days
            if minutes > 10080:
                await ctx.send("Time cannot exceed 7 days.")
                return
        # Get current time in UTC to calculate the end time of the mute
        start_date = datetime.datetime.utcnow()
        end_date = start_date + datetime.timedelta(minutes=minutes)
        # Remember the member ID just in case the member leaves mid-mute
        memberid = member.id
        # Inform that the member will be muted until end_date
        await ctx.send("{.name} will be muted until {}".format(member, end_date.strftime("%B %d, %I:%M %p UTC")))
        conn = sqlite3.connect('fhbot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO mutes (memberid, endtime, issuer) VALUES (?, ?, ?)", (memberid, end_date.strftime("%B %d, %I:%M:%S %p"), ctx.author.id,))
        conn.commit()
        conn.close()
        # Wait for the unmute action
        await asyncio.sleep(minutes * 60)
        conn = sqlite3.connect('fhbot.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM mutes WHERE memberid=?', (memberid,))
        try:
            await member.remove_roles(muted_role)
        except:
            print("Member has left and can't be unmuted")
        conn.commit()
        conn.close()
        print("{.name} was unmuted.".format(member))
    else:
        # If no time was specified, the member will be muted indefinitely
        conn = sqlite3.connect('fhbot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO mutes (memberid, issuer) VALUES (?, ?)", (member.id, ctx.author.id))
        conn.commit()
        conn.close()
        await ctx.send("{.name} was muted.".format(member))
@mute.error
async def mute_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.BadArgument):
        await ctx.send("Member not found.")
        print("{.author} attempted to run the command 'mute' and was met with {}: {}".format(ctx, type(error), error))

async def createMuteRole(guild: discord.Guild):
    # Used for checking if the muted role has already been created
    role_exists = False
    # Create the permissions object for the role
    perms = discord.Permissions(permissions=0)
    # Initialise the role, just in case
    muted_role = None
    # Check the roles to see if the FHmuted role is already created
    for role in guild.roles:
        if role.name == "FHmuted":
            role_exists = True
            muted_role = role
    # If the role is not already created, create it with permissions created above
    if not role_exists:
        muted_role = await guild.create_role(name="FHmuted", permissions=perms)
    # Create channel overrides for the muted role so the person can't send messages, files or add reactions. They also can't speak, connect or stream on voice channels
    for channel in guild.text_channels:
        await channel.set_permissions(muted_role, send_messages=False, add_reactions=False, send_tts_messages=False, attach_files=False)
    for channel in guild.voice_channels:
        await channel.set_permissions(muted_role, speak=False, connect=False, stream=False)
    return muted_role

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    # Checks if the defined person has the mute role
    isMuted = False
    for role in member.roles:
        isMuted = role.name == "FHmuted"
        if isMuted:
            print("Member is muted")
            mutedRole = role
    # If the member is muted, remove the mute
    if isMuted:
        conn = sqlite3.connect('fhbot.db')
        print("connected to database")
        cursor = conn.cursor()
        print("created a cursor")
        cursor.execute('DELETE FROM mutes WHERE memberid=?', (member.id,))
        print("executed the delete command")
        conn.commit()
        print("saved the changes")
        conn.close()
        print("closed the connection")
        await member.remove_roles(mutedRole)
        await ctx.send("{} was unmuted.".format(member))
        print("{.name} was unmuted.".format(member))
    # If the member is not muted, inform about the fact
    else:
        await ctx.send("Member is not muted.")
@unmute.error
async def unmute_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.BadArgument):
        await ctx.send("Member not found.")
        print("{.author} attempted to run the command 'unmute' and was met with {}: {}".format(ctx, type(error), error))

@bot.command()
@commands.has_permissions(kick_members=True)
async def testwelcome(ctx):
    # For testing the welcoming image
    await on_member_join(ctx.author)

# VOICE CHANNEL COMMANDS
@bot.command()
async def join(ctx):
    # Save the command issuer's voice state
    voicestate = ctx.author.voice
    # Check if the bot is already connected somewhere
    if len(bot.voice_clients) > 0:
        botchannel = bot.voice_clients[0].channel
        # Check if the bot is currently on VC with others or is still playing something
        if len(botchannel.members) > 1 or bot.voice_clients[0].is_playing():
            await ctx.send("I'm currently occupied on {}.".format(botchannel))
            return
        # Check if the command issuer is not connected to a voice channel
        elif voicestate is None:
            await ctx.send("You are not connected to a voice channel.")
            return
        # If above checks were false, disconnect from the channel
        else:
            await bot.voice_clients[0].disconnect()
    
    # If the command issuer is connected on a voice channel, join on the same channel
    if voicestate is not None:
        channel = voicestate.channel
        await channel.connect()
    else:
        await ctx.send("You are not connected to a voice channel.")

g_queue = []

@bot.command()
async def leave(ctx):
    global g_queue
    botchannel = bot.voice_clients[0].channel
    # Check that the command issuer is on the voice channel before disconnecting
    if await isOnChannel(ctx.author, botchannel):
        bot.voice_clients[0].stop()
        await bot.voice_clients[0].disconnect()
        g_queue.clear
        files = os.listdir("audio")
        print(files)

@bot.command()
async def play(ctx, *, search: str):
    global g_queue
    voiceclient = bot.voice_clients[0]
    botchannel = voiceclient.channel
    currentsong = len(g_queue)
    # Check if the user is not in the same voice channel
    if not await isOnChannel(ctx.author, botchannel):
        return
    # Check if the search is a YouTube URL
    url = re.findall(r'http[s]?://(?:www\.)?youtu.*', search)
    # If there is no URL, use the search
    if len(url) is 0:
        print(search)
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'audio/song{}.%(etx)s'.format(currentsong),
            'quiet': False
            }

        bot_message = await ctx.send("Preparing...")
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url[0]])
            title = ydl.extract_info(url[0]).get("title")
        g_queue.append(currentsong)
        if voiceclient.is_playing():
            await bot_message.edit(content="Added **{}** to queue".format(title))
        else:
            await bot_message.edit(content="Playing **{}**".format(title))
            voiceclient.play(discord.FFmpegPCMAudio("audio/song{}.mp3".format(currentsong)), after=lambda: checkQueue(voiceclient, currentsong))
@play.error
async def play_error(ctx, error):
    # If the user didn't include a search term
    if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
        await ctx.send("Usage: `play [YouTube URL/search term]`")

# Function to check if the user shares a voice channel with the bot
async def isOnChannel(member: discord.Member, channel: discord.VoiceChannel):
    return member in channel.members

def checkQueue(voice_client, lastPlayed: int):
    print("Checking queue")
    global g_queue
    g_queue.pop(0)
    if lastPlayed+1 in g_queue:
        currentsong = g_queue.pop(0)
        voice_client.play(discord.FFmpegPCMAudio("audio/song{}.mp3".format(currentsong)), after=lambda: checkQueue(voice_client, currentsong))

# INFO COMMANDS
@bot.command()
async def stats(ctx, member: typing.Optional[discord.Member], channel: typing.Optional[discord.TextChannel], messagecount: int):
    # Default to command issuer in the current channel
    if member is None:
        member = ctx.author
    if channel is None:
        channel = ctx.message.channel
    # Get the member's joining date to check messages after (might be a long time, may need to limit this to save in processing time)
    join_date = member.joined_at
    # Inform that the bot is calculating the statistics
    botmessage = await ctx.send("Calculating...")
    # Put all the messages in a list
    messages = await channel.history(limit=None, after=join_date, oldest_first=False).flatten()
    # Combined length of all messages, the number of attachments in those messages and the number of messages checked
    combinedLength = 0
    totalAttachments = 0
    user_messages = 0
    for message in messages:
        # Only handle the message if it's sent by the member we want
        if message.author == member:
            combinedLength += len(message.clean_content)
            totalAttachments += len(message.attachments)
            user_messages += 1
        # Once the wanted number of messages has been checked, quit going through the messages
        if user_messages == messagecount:
            break
    # If the member doesn't have any messages in the specified channel, inform about it
    if user_messages == 0:
        averageLength = 0
        embed = discord.Embed(title="{.name} has no messages in {}".format(member, channel))
    # Otherwise show the stats
    else:
        averageLength = round(combinedLength / user_messages, 2)
        embed = discord.Embed(title="Stats for {.name} for the past {} messages in {}".format(member, user_messages, channel), color=0x0ffca9)
        embed.add_field(name="Average message length", value="{} characters".format(averageLength))
        embed.add_field(name="Total attachments", value="{} attachments".format(totalAttachments))
    await botmessage.edit(content=None, embed=embed)

# HELP COMMANDS
# Command for listing all available commands and their function
@bot.command()
async def commands(ctx, arg: str):
    # List all admin commands
    if arg.lower() == "admin":
        embed = discord.Embed(title="Admin commands", description="<required> [optional]", color=0x7f00ff)
        embed.add_field(name="kick <@member> [reason]", value="Kicks a member with an optional reason.", inline=False)
        embed.add_field(name='ban <@member/ID> [days of messages deleted (max 7, default 0)] [reason]', value="Bans a user by ID or tag with optional amount of messages deleted and reason.", inline=False)
        embed.add_field(name="unban <ID> [reason]", value="Unbans a user by ID.", inline=False)
        embed.add_field(name="warn <@member> <reason>", value="Warns a member with given reason.", inline=False)
        embed.add_field(name="warnings <@member>", value="Lists the warnings of a member.", inline=False)
        embed.add_field(name="removewarn <ID>", value="Removes a warning with the given ID number.", inline=False)
        embed.add_field(name="mute <@member> [time]", value="Mutes a member from chatting and voice chatting with optional time (max 7d). Time units are m, h and d. E.g. `mute @john 2d 5h 15m`", inline=False)
        embed.add_field(name="testwelcome", value="Displays the welcoming message as if a new member joined.", inline=False)
        await ctx.send(embed=embed)
    # Lists all music commands
    elif arg.lower() == "music":
        embed = discord.Embed(title="Music commands", description="<required> [optional]", color=0x208afc)
        embed.add_field(name="join", value="Makes the bot join your voice channel.", inline=False)
        embed.add_field(name="leave", value="Makes the bot leave the current voice channel.", inline=False)
        embed.add_field(name="play <URL>", value="Plays a song from a YouTube URL.", inline=False)
        await ctx.send(embed=embed)
    # Lists all information commands
    elif arg.lower() == "info":
        embed = discord.Embed(title="Info commands", description="<required> [optional]", color=0x0ffca9)
        embed.add_field(name="stats [@member] [#channel] <messages>", value="Shows stats of the past <messages> messages, like average length. Defaults to yourself and the current channel", inline=False)
        await ctx.send(embed=embed)
@commands.error
async def commands_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
        # If no category is specified, list all available categories
        await ctx.send("Usage: commands <category>\n__**Categories**__\n**Admin**: Admin commands\n**Music**: Music commands\n**Info**: Information about the guild and its members")

async def statusChanger():
    games = [
        "to steal the pancakes",
        "root beer drinking game",
        "with trash pandas",
        "with a ban knif",
        "tickling the toe beans",
        "with the cute beans",
        "pineapples",
        "dead like extinct sonas",
    ]
    while True:
        game = discord.Game(random.choice(games))
        await bot.change_presence(activity=game)
        await asyncio.sleep(20)


bot.run(TOKEN)
