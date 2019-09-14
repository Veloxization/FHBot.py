import discord
import sys
import sqlite3
import typing
import asyncio
import datetime
import requests
import os
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from discord.ext import commands

TOKEN = 'NjEyNzE4MjU1NjM4ODM5MzA4.XVmccQ.nBZB73prpOvrIab84VMjGj0BFes' # Not a real token. Demonstration purposes only.
bot = commands.Bot(command_prefix='$')

@bot.event
async def on_ready():
    print("Logged on as {.user}!".format(bot))
    print("Running version {}".format(sys.version))

@bot.event
async def on_member_join(member):
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
async def ban(ctx, member: typing.Union[discord.User, int], days: typing.Optional[int] = 0, *reason: str):
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
    # Combine the reason so the user doesn't have to use quotations
    full_reason = " ".join(word for word in reason)
    # Ban the member, remove the messages and delete the specified amount of messages (default 0), also inform about the action
    await ctx.message.guild.ban(discord.Object(id=memberid), reason=full_reason, delete_message_days=days)
    await ctx.send("<@{}> was banned.".format(memberid))
    print("{.author} banned {} with reason: {}".format(ctx, member, full_reason))
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
async def unban(ctx, memberid: int, *reason):
    # Combine the reason so the user doesn't have to use quotations, unban the member and inform about it
    full_reason = " ".join(word for word in reason)
    await ctx.guild.unban(discord.Object(id=memberid), reason=full_reason)
    await ctx.send("<@{}> was unbanned.".format(memberid))
    print("{.author} unbanned {} with reason: {}".format(ctx, memberid, full_reason))

@bot.command()
@commands.has_permissions(ban_members=True)
async def warn(ctx, member: discord.Member, *reason: str):
    # Check if the user tagged a proper member
    try:
        warnedid = member.id
    except:
        ctx.send("Member not found.")
    # Combine the reason so the user doesn't have to use quotations
    full_reason = " ".join(word for word in reason)
    # Check that the user actually provides a reason
    if full_reason == "":
        await ctx.send("Please include a reason for logging purposes.")
        return
    # Connect to the Sqlite database and save the warning there
    conn = sqlite3.connect('fhbot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO warnings (memberid, reason, issuerid) VALUES (?, ?, ?)', (warnedid, full_reason, ctx.message.author.id))
    conn.commit()
    conn.close()
    # Inform about the warning and send a message to the user who was warned
    print("{.author} warned {} for: {}".format(ctx, member, full_reason))
    await ctx.send("{.mention} was warned.".format(member))
    await member.send("You were warned for: {}".format(full_reason))

@bot.command()
@commands.has_permissions(ban_members=True)
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
@commands.has_permissions(ban_members=True)
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
async def mute(ctx, member: discord.Member, *time: typing.Optional[str]):
    # Used for checking if the muted role has already been created
    role_exists = False
    # Create the permissions object for the role
    perms = discord.Permissions(permissions=0)
    # Initialise the role, just in case
    muted_role = None
    # Check the roles to see if the FHmuted role is already created
    for role in ctx.guild.roles:
        if role.name == "FHmuted":
            role_exists = True
            muted_role = role
    # If the role is not already created, create it with permissions created above
    if not role_exists:
        muted_role = await ctx.guild.create_role(name="FHmuted", permissions=perms)
    # Create channel overrides for the muted role so the person can't send messages, files or add reactions. They also can't speak, connect or stream on voice channels
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(muted_role, send_messages=False, add_reactions=False, send_tts_messages=False, attach_files=False)
    for channel in ctx.guild.voice_channels:
        await channel.set_permissions(muted_role, speak=False, connect=False, stream=False)
    # Add the created role to the muted member
    await member.add_roles(muted_role)
    # If time was specified, go for the timed unmute
    if time is not None:
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
        # Inform that the member will be muted until end_date
        await ctx.send("{.name} will be muted until {}".format(member, end_date.strftime("%B %d, %I:%M %p UTC")))
        # Wait for the unmute action
        await asyncio.sleep(minutes * 60)
        await member.remove_roles(muted_role)
        print("{.name} was unmuted.".format(member))
    else:
        # If no time was specified, the member will be muted indefinitely
        await ctx.send("{.name} was muted.".format(member))

@bot.command()
@commands.has_permissions(kick_members=True)
async def testwelcome(ctx):
    # For testing the welcoming image
    await on_member_join(ctx.author)

@bot.command()
# Command for listing all available commands and their function
async def commands(ctx, *arg):
    # List all admin commands
    if "".join(arg).lower() == "admin":
        embed = discord.Embed(title="Admin commands", description="[optional]", color=0x7f00ff)
        embed.add_field(name="kick @member [reason]", value="Kicks a member with an optional reason.", inline=False)
        embed.add_field(name='ban @member/ID [days of messages deleted (max 7, default 0)] [reason]', value="Bans a user by ID or tag with optional amount of messages deleted and reason.", inline=False)
        embed.add_field(name="unban ID [reason]", value="Unbans a user by ID.", inline=False)
        embed.add_field(name="warn @member reason", value="Warns a member with given reason.", inline=False)
        embed.add_field(name="warnings @member", value="Lists the warnings of a member.", inline=False)
        embed.add_field(name="removewarn ID", value="Removes a warning with the given ID number.", inline=False)
        embed.add_field(name="mute @member [time]", value="Mutes a member from chatting and voice chatting with optional time (max 7d). Time units are m, h and d. E.g. mute @john 2d 5h 15m", inline=False)
        embed.add_field(name="testwelcome", value="Displays the welcoming message as if a new member joined.", inline=False)
        await ctx.send(embed=embed)
    else:
        # If no category is specified, list all available categories
        await ctx.send("Usage: commands [category]\n__**Categories**__\n**Admin**: Admin commands")


bot.run(TOKEN)
