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

TOKEN = 'NjEyNzE4MjU1NjM4ODM5MzA4.XVmccQ.nBZB73prpOvrIab84VMjGj0BFes'
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
    kicked_list = ", ".join(member.name for member in members)
    full_reason = " ".join(word for word in reason)
    await ctx.send("{} not kicked because the command is not ready yet but the reason was {}".format(kicked_list, full_reason))

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: typing.Union[discord.User, int], days: typing.Optional[int] = 0, *reason: str):
    memberid = 0
    if type(member) is int:
        memberid = member
    else:
        memberid = member.id
    if days > 7:
        days = 7
    full_reason = " ".join(word for word in reason)
    await ctx.message.guild.ban(discord.Object(id=memberid), reason=full_reason, delete_message_days=days)
    await ctx.send("<@{}> was banned.".format(memberid))
    print("{.author} banned {} with reason: {}".format(ctx, member, full_reason))
@ban.error
async def ban_error(ctx, error):
    if isinstance(error, discord.ext.commands.BadUnionArgument):
        await ctx.send("Member not found.")
    elif isinstance(error, discord.ext.commands.errors.CommandInvokeError):
        await ctx.send("User not found.")
    else:
        print("{.author} attempted to run the command 'ban' and was met with {}: {}".format(ctx, type(error), error))

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, memberid: int, *reason):
    full_reason = " ".join(word for word in reason)
    await ctx.guild.unban(discord.Object(id=memberid), reason=full_reason)
    await ctx.send("<@{}> was unbanned.".format(memberid))
    print("{.author} unbanned {} with reason: {}".format(ctx, memberid, full_reason))

@bot.command()
@commands.has_permissions(ban_members=True)
async def warn(ctx, member: discord.Member, *reason: str):
    try:
        warnedid = member.id
    except:
        ctx.send("Member not found.")
    warnedmention = member.mention
    full_reason = " ".join(word for word in reason)
    if full_reason == "":
        await ctx.send("Please include a reason for logging purposes.")
        return
    conn = sqlite3.connect('fhbot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO warnings (memberid, reason, issuerid) VALUES (?, ?, ?)', (warnedid, full_reason, ctx.message.author.id))
    conn.commit()
    conn.close()
    print("{.author} warned {} for: {}".format(ctx, member, full_reason))
    await ctx.send("{} was warned.".format(warnedmention))
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
    try:
        memberid = member.id
    except:
        await ctx.send("Member not found.")
        return
    conn = sqlite3.connect('fhbot.db')
    cursor = conn.cursor()
    title = "Warnings of {.display_name}".format(member)
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
    role_exists = False
    perms = discord.Permissions(permissions=0)
    muted_role = None
    for role in ctx.guild.roles:
        if role.name == "FHmuted":
            role_exists = True
            muted_role = role
    if not role_exists:
        muted_role = await ctx.guild.create_role(name="FHmuted", permissions=perms)
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(muted_role, send_messages=False, add_reactions=False, send_tts_messages=False, attach_files=False)
    for channel in ctx.guild.voice_channels:
        await channel.set_permissions(muted_role, speak=False, connect=False, stream=False)
    await member.add_roles(muted_role)
    if time is not None:
        minutes = 0
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
        start_date = datetime.datetime.utcnow()
        end_date = start_date + datetime.timedelta(minutes=minutes)
        await ctx.send("{.name} will be muted until {}".format(member, end_date.strftime("%B %d, %I:%M %p UTC")))
        await asyncio.sleep(minutes * 60)
        await member.remove_roles(muted_role)
        print("{.name} was unmuted.".format(member))
    else:
        await ctx.send("{.name} was muted.".format(member))

@bot.command()
@commands.has_permissions(kick_members=True)
async def testwelcome(ctx):
    await on_member_join(ctx.author)

@bot.command()
async def commands(ctx, *arg):
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
        await ctx.send("Usage: commands [category]\n__**Categories**__\n**Admin**: Admin commands")


bot.run(TOKEN)
