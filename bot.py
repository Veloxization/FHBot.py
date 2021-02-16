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
import json
import lavalink #for musicbot!!!
import emoji
from io import BytesIO
from unqlite import UnQLite
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from urllib import parse
from discord.ext import commands

TOKEN = 'NjEyNzE4MjU1NjM4ODM5MzA4.XVmccQ.nBZB73prpOvrIab84VMjGj0BFes' # Not a real token. Demonstration purposes only.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', case_insensitive=True, help_command=None, intents=intents)
G_logChannel = None
G_greetingChannel = None
G_confirmationChannel = None
G_startingRole = None
G_confirmedRole = None
G_mutedRole = None

@bot.event
async def on_ready():
    print(f"Logged on as {bot.user}!")
    print(f"Running version {sys.version}")
    global G_logChannel
    global G_greetingChannel
    global G_confirmationChannel
    global G_startingRole
    global G_confirmedRole
    bot.add_cog(Logging(bot))
    bot.add_cog(Moderator(bot))
    bot.add_cog(Utility(bot))
    bot.add_cog(Info(bot))
    bot.add_cog(Fun(bot))
    bot.add_cog(Help(bot))
    db = UnQLite("FHDatabase.db")
    channels = db.collection("Channels")
    fetched = channels.filter(lambda obj: obj["name"] == "logs")[0]["id"]
    if fetched != None:
        G_logChannel = bot.get_channel(fetched)

    fetched = channels.filter(lambda obj: obj["name"] == "greetings")[0]["id"]
    if fetched != None:
        G_greetingChannel = bot.get_channel(fetched)

    fetched = channels.filter(lambda obj: obj["name"] == "confirmation")[0]["id"]
    if fetched != None:
        G_confirmationChannel = bot.get_channel(fetched)
    db.close()
    await statusChanger()

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None

    def calculateUserAge(self, member: discord.Member):
        timeNow = datetime.datetime.utcnow()
        userCreated = member.created_at
        account_age = timeNow - userCreated
        years = account_age.days // 365
        months = (account_age.days - (years * 365)) // 30
        days = account_age.days - (years * 365) - (months * 30)
        hours = account_age.seconds // 3600
        minutes = (account_age.seconds - (hours * 3600)) // 60
        seconds = account_age.seconds - (hours * 3600) - (minutes * 60)
        age = {"years": years, "months": months, "days": days, "hours": hours, "minutes": minutes, "seconds": seconds}
        age_string = ""
        if age["years"] == 1:
            age_string = age_string + "1 year, "
        elif age["years"]:
            age_string = age_string + f"{age['years']} years, "
        if age["months"] == 1:
            age_string = age_string + "1 month, "
        elif age["months"]:
            age_string = age_string + f"{age['months']} months, "
        if age["days"] == 1:
            age_string = age_string + "1 day, "
        elif age["days"]:
            age_string = age_string + f"{age['days']} days, "
        if not age["years"] and not age["months"]:
            if age["hours"] == 1:
                age_string = age_string + "1 hour, "
            elif age["hours"]:
                age_string = age_string + f"{age['hours']} hours, "
            if age["minutes"] == 1:
                age_string = age_string + "1 minute, "
            elif age["minutes"]:
                age_string = age_string + f"{age['minutes']} minutes, "
            if age["seconds"] == 1:
                age_string = age_string + "1 second, "
            elif age["seconds"]:
                age_string = age_string + f"{age['seconds']} seconds, "
        return age_string[:-2]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        global G_logChannel
        # Check if the member was muted and reapply it, just in case someone is trying to avoid a mute by rejoining the server
        db = UnQLite("FHDatabase.db")
        mutes = db.collection("Mutes")
        fetched = mutes.filter(lambda obj: obj["id"] == member.id)
        if fetched:
            muted_role = await createMuteRole(member.guild)
            await member.add_roles(muted_role)
        # Notify about the member joining in logs
        embed = discord.Embed(title="Member Joined", description=f"{member.mention} joined the server!", color=0x00ff00)
        embed.set_thumbnail(url=member.avatar_url)
        age = self.calculateUserAge(member)
        embed.add_field(name="Account Age", value=age, inline=False)
        await G_logChannel.send(embed=embed)
        print(f"User joined with an account that is {age} old.")

        # Give the user a joining role
        roles = db.collection("Roles")
        roleid = roles.filter(lambda obj: obj["name"] == "read_the_rules")[0]["id"]
        startingRole = member.guild.get_role(roleid)
        await member.add_roles(startingRole)

        # Message the user with the specified welcoming message
        greetings = db.collection("BotGreetings")
        dm_message = greetings.filter(lambda obj: obj["name"] == "greeting_dm")[0]["content"]
        try:
            await member.send(dm_message.replace("$[mention]", f"{member.mention}").replace("$[user]", f"{member.name}"))
        except:
            print(f"Couldn't message {member.name}")

        # Store the new member info in the database, "warned" is for inactivity warning
        new_members = db.collection("NewMembers")
        new_members.store({'id': member.id, 'member_number': member.guild.member_count, 'warned': False})
        db.close()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        global G_logChannel
        embed = discord.Embed(title="Member Left", description=f"{member.mention} left the server", color=0xff7f00)
        embed.set_author(name=member, icon_url=member.avatar_url)
        roles = ""
        for role in member.roles:
            if role.name != "@everyone":
                roles += f"{role.mention}, "
        roles = roles[:-2]
        embed.add_field(name="Roles", value=roles, inline=False)
        await G_logChannel.send(embed=embed)
        # Remove the new member information from the database to save space
        db = UnQLite("FHDatabase.db")
        new_members = db.collection("NewMembers")
        fetched = new_members.filter(lambda obj: obj["id"] == member.id)
        # Only activate on members who haven't gone through rule confirmation
        if fetched:
            id = fetched[0]["__id"]
            new_members.delete(id)

    @commands.Cog.listener()
    async def on_message(self, message):
        global G_confirmationChannel
        global G_greetingChannel
        db = UnQLite("FHDatabase.db")
        if message.channel == G_confirmationChannel:
            roles = db.collection("Roles")
            passphrases = db.collection("Passphrases")
            passphrase_found = False
            for passphrase in passphrases.all():
                if passphrase["content"] in message.content:
                    passphrase_found = True
            if passphrase_found:
                try:
                    await message.delete()
                except:
                    print("Too slow! Rule confirmation message was already deleted by someone else.")
                role = roles.filter(lambda obj: obj["name"] == "newbie")[0]["id"]
                confirmedRole = message.guild.get_role(role)
                await message.author.add_roles(confirmedRole)
                role = roles.filter(lambda obj: obj["name"] == "read_the_rules")[0]["id"]
                startingRole = message.guild.get_role(role)
                await message.author.remove_roles(startingRole)
                new_members = db.collection("NewMembers")
                fetched = new_members.filter(lambda obj: obj["id"] == message.author.id)
                # If the member is found in the database, use the member number there. Otherwise use the number from API
                if fetched:
                    member_number = fetched[0]["member_number"]
                else:
                    member_number = message.guild.member_count
                welcome_message, imageFile, location = await create_welcome(message.author, member_number)
                await G_greetingChannel.send(welcome_message, file=imageFile)
                os.remove(location)
                # Only activate on members who joined after the change
                if fetched:
                    id = fetched[0]["__id"]
                    new_members.delete(id)
        db.close()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        global G_logChannel
        roles_before = before.roles
        roles_after = after.roles
        if before.nick != after.nick:
            db = UnQLite("FHDatabase.db")
            nicknames = db.collection("Nicknames")
            fetched = nicknames.filter(lambda obj: obj["id"] == after.id and obj["nickname"] == before.nick)
            if (before.nick != None and not fetched):
                nicknames.store({"id": after.id, "nickname": before.nick})
                fetched = nicknames.filter(lambda obj: obj["id"] == after.id)
                if len(fetched) > 10:
                    nicknames.delete(fetched[0]["__id"])
            embed = discord.Embed(title="Nickname Updated", description=f"{after.mention} had their nickname changed.", color=after.color)
            embed.set_author(name=after, icon_url=after.avatar_url)
            embed.add_field(name="Previously", value=before.nick, inline=True)
            embed.add_field(name="Now", value=after.nick, inline=True)
            await G_logChannel.send(embed=embed)
            db.close()
        roles_removed = [role for role in before.roles if not role in after.roles]
        roles_added = [role for role in after.roles if not role in before.roles]
        if roles_removed:
            embed = discord.Embed(title="Role Removed", description=f"{after.mention} was removed from {roles_removed[0].mention}", color=after.color)
            embed.set_author(name=after, icon_url=after.avatar_url)
            await G_logChannel.send(embed=embed)
        elif roles_added:
            embed = discord.Embed(title="Role Added", description=f"{after.mention} was added to {roles_added[0].mention}", color=after.color)
            embed.set_author(name=after, icon_url=after.avatar_url)
            await G_logChannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        global G_logChannel
        # The member's ID to be saved in the database
        memberid = before.id
        # Get the user as a member to grab their role colour for embed colour
        member = bot.get_guild(223340988314157056).get_member(memberid)
        # The avatar's URL before and after update
        avatar_before = before.avatar_url
        avatar_after = after.avatar_url
        # The avatar's hash before and after update
        avahash_before = before.avatar
        avahash_after = after.avatar
        # If the usernames don't match, the user has changed their username
        if before.name != after.name:
            db = UnQLite("FHDatabase.db")
            usernames = db.collection("Usernames")
            fetched = usernames.filter(lambda obj: obj["id"] == after.id and obj["username"] == before.name)
            if(not fetched):
                usernames.store({"id": after.id, "username": before.name})
                fetched = usernames.filter(lambda obj: obj["id"] == after.id)
                if len(fetched) > 10:
                    usernames.delete(fetched[0]["__id"])
            embed = discord.Embed(title="Username Updated", description=f"{member.mention} updated their username", color=member.color)
            embed.set_author(name=after, icon_url=avatar_after)
            embed.add_field(name="Previously", value=before.name, inline=True)
            embed.add_field(name="Now", value=after.name, inline=True)
            await G_logChannel.send(embed=embed)
            db.close()
        # If the avatar hashes don't match, the user changed their avatar
        if avahash_before != avahash_after:
            embed = discord.Embed(title="Avatar Updated", description=f"{member.mention} updated their avatar", color=member.color)
            embed.set_author(name=after, icon_url=avatar_before)
            embed.set_thumbnail(url=avatar_after)
            await G_logChannel.send(embed=embed)

    @bot.event
    async def on_bulk_message_delete(messages):
        global G_logChannel
        # Name of the log file in the form of year-month-day-hour-minute-second-microsecond.txt
        filename = f"{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')}.txt"
        # Start the file with a title: "Bulk message deletion:" and specify the time of the deletion
        content = f"Bulk message deletion: {datetime.datetime.utcnow().strftime('%A, %B %d %Y, %H:%M:%S UTC')}\n----------\n"
        # Specify how many messages were deleted
        content += f"{len(messages)} messages\n\n"
        # Specify whose message was deleted, their ID, what time the message was deleted, and what the message content was
        for message in messages:
            content += f"From {message.author} ({message.author.id}) at {message.created_at.strftime('%B %d, %H:%M UTC')} in #{message.channel.name}\n"
            content += f"{message.clean_content}\n\n"
        # Save the file to logs directory with the specified name
        with open(f"logs/{filename}", "w") as text_file:
            text_file.write(content)
        logFile = discord.File(f"logs/{filename}")
        await G_logChannel.send(f"**Bulk Message Deletion**: {len(messages)} messages logged", file=logFile)
        os.remove(f"logs/{filename}")

        print(f"{len(messages)} messages deleted, log saved on server")

    @bot.event
    async def on_message_delete(message):
        global G_logChannel
        embed = discord.Embed(title="Message Deleted", description=f"Message in {message.channel.mention} by {message.author.mention} was deleted.", color=0xfc7805)
        embed.set_author(name=message.author, icon_url=message.author.avatar_url)
        if message.content is None:
            embed.add_field(name="Content", value="**Cannot retrieve content**", inline=False)
        elif message.content.startswith("$feedback "):
            return
        else:
            embed.add_field(name="Content", value=message.content, inline=False)
        await G_logChannel.send(embed=embed)

    @bot.event
    async def on_message_edit(before, after):
        # Ignore if the message author is a bot or if the message "edit" is just an embed appearing
        if after.author.bot or (not before.embeds and after.embeds):
            return
        global G_logChannel
        embed = discord.Embed(title="Message Edited", description=f"Message in {after.channel.mention} by {after.author.mention} was edited. [Jump to message]({after.jump_url})", color=0x05fceb)
        embed.set_author(name=after.author, icon_url=after.author.avatar_url)
        if not before.content or not after.content:
            embed.add_field(name="Content", value="**Cannot retrieve content**", inline=False)
        else:
            before_message = before.content
            if len(before_message) > 250:
                before_message = before_message[:250]
                before_message += "..."
            after_message = after.content
            if len(after_message) > 250:
                after_message = after_message[:250]
                after_message += "..."
            embed.add_field(name="Previously", value=f"\u200b{before_message}", inline=False)
            embed.add_field(name="Now", value=f"\u200b{after_message}", inline=False)
        await G_logChannel.send(embed=embed)

# Create a user action the bot listens to which will grant the user another role

async def create_welcome(member: discord.Member, memberNumber: int):
    # CREATE THE WELCOMING BANNER
    # name of the banner image with file extension
    banner_name = "banner.png"
    # open the banner file and resize it to 1000x300 px, save the height to variable
    im1 = Image.open(f"images/{banner_name}").resize((1000, 300))
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
    font = ImageFont.truetype(f"fonts/{font_name}", font_size)
    # determine the welcoming text to use and draw it on top of the banner, 300px from the left and centered by the height of the text and amount of lines, lambda function to get the ordinal number
    ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(math.floor(n/10)%10!=1)*(n%10<4)*n%10::4])
    member_ordinal = ordinal(memberNumber)
    db = UnQLite("FHDatabase.db")
    greetings = db.collection("BotGreetings")
    welcome_message = greetings.filter(lambda obj: obj["name"] == "greeting_message")[0]["content"]
    welcome_text = greetings.filter(lambda obj: obj["name"] == "greeting_image")[0]["content"]
    welcome_message = welcome_message.replace("$[mention]", f"{member.mention}").replace("$[user]", f"{member.name}").replace("$[nth]", f"{member_ordinal}").replace("$[n]", f"{member.guild.member_count}")
    welcome_text = welcome_text.replace("$[user]", f"{member.name}").replace("$[nth]", f"{member_ordinal}").replace("$[n]", f"{member.guild.member_count}")
    text_w, text_h = font.getsize(welcome_text)
    draw.text((300, (im1_h - text_h) / 2), welcome_text, font=font, fill=(255,255,255,255), stroke_width=2, stroke_fill=(0,0,0,255))
    # save the created file as an image file and send it to the determined channel
    location = f"images/{member.id}_welcome.png"
    im1.save(location)
    imagefile = discord.File(f"images/{member.id}_welcome.png")
    db.close()
    return welcome_message, imagefile, location

class Moderator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# MODERATOR ONLY COMMANDS
    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: typing.Optional[str]):
        await add_to_logs(ctx.message.content, ctx.author)
        await member.kick(reason=reason)
        await ctx.send(f"{member.name} was kicked")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: typing.Union[discord.User, int], delete: typing.Optional[int] = 0, *, reason: typing.Optional[str]):
        await add_to_logs(ctx.message.content, ctx.author)
        # Initialise the member ID just in case
        memberid = 0
        # Check if the user entered an ID or tagged a member
        if type(member) is int:
            memberid = member
        else:
            memberid = member.id
        # The bot can't remove messages older than 7 days, so change any number greater than 7 to 7
        if delete > 7:
            delete = 7
        # Ban the member and delete the specified amount of messages (default 0), also inform about the action
        await ctx.message.guild.ban(discord.Object(id=memberid), reason=reason, delete_message_days=delete)
        await ctx.send(f"<@!{memberid}> was banned.")
        print(f"{ctx.author} banned {member} with reason: {reason}")
    @ban.error
    async def ban_error(self, ctx, error):
        # Catch any errors if the user enters an invalid name or ID
        if isinstance(error, discord.ext.commands.BadUnionArgument):
            await ctx.send("Member not found.")
        elif isinstance(error, discord.ext.commands.errors.CommandInvokeError):
            await ctx.send("User not found.")
        else:
            print(f"{ctx.author} attempted to run the command 'ban' and was met with {type(error)}: {error}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, memberid: int, *, reason: typing.Optional[str]):
        await add_to_logs(ctx.message.content, ctx.author)
        # Unban the member and inform about it
        await ctx.guild.unban(discord.Object(id=memberid), reason=reason)
        await ctx.send(f"<@!{memberid}> was unbanned.")
        print(f"{ctx.author} unbanned {memberid} with reason: {reason}")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason):
        await add_to_logs(ctx.message.content, ctx.author)
        # Check if the user tagged a proper member
        try:
            warnedid = member.id
        except:
            await ctx.send("Member not found.")
        # Connect to the database and save the warning there
        db = UnQLite("FHDatabase.db")
        warnings = db.collection("Warnings")
        warnings.store({"id": warnedid, "reason": reason, "issuer": ctx.author.id})
        db.close()
        # Inform about the warning and send a message to the user who was warned
        print(f"{ctx.author} warned {member} for: {reason}")
        await ctx.send(f"{member.mention} was warned.")
        try:
            await member.send(f"You were warned for: {reason}")
        except:
            print(f"Unable to message {member} with the warning message")

    @warn.error
    async def warn_error(self, ctx, error):
        # Check that the user actually includes a reason
        if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
            await ctx.send("Please include a reason for logging purposes.")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def removewarn(self, ctx, arg: int):
        await add_to_logs(ctx.message.content, ctx.author)
        # check that the user enters an integer
        try:
            warnid = int(arg)
        except ValueError:
            await ctx.send(f'{arg} is not a valid ID.')
            return
        # connect to database and check if a warning with selected ID is found
        db = UnQLite("FHDatabase.db")
        warnings = db.collection("Warnings")
        fetched = warnings.filter(lambda obj: obj["__id"] == warnid)
        # if no warning is found, inform the user and end the function
        if not fetched:
            await ctx.send(f"No warnings with ID {warnid} found.")
            return
        else:
            fetched = fetched[0]
        # in case of a typo, confirm that the warning is the correct one and ask the user to add a reaction accordingly
        bot_message = await ctx.send(f'Are you sure you want to remove `{fetched["reason"]}` from <@!{fetched["id"]}>?')
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
                print(f'{ctx.author} removed warning {fetched["reason"]} from {fetched["id"]}')
                await bot_message.edit(content=f'Warning {fetched["reason"]} removed from <@!{fetched["id"]}>')
                await bot_message.clear_reactions()
                warnings.delete(warnid)
                db.close()
            elif reaction.emoji == "❌":
                await bot_message.delete()

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warnings(self, ctx, member: discord.Member):
        await add_to_logs(ctx.message.content, ctx.author)
        # Check if the user tagged a proper member
        try:
            memberid = member.id
        except:
            await ctx.send("Member not found.")
            return
        # Connect to the database and get the warnings of the specified user
        db = UnQLite("FHDatabase.db")
        # Collect the warnings into an embed and show the warning's ID, issuer and the reason
        warnings = db.collection("Warnings")
        fetched = warnings.filter(lambda obj: obj["id"] == memberid)
        embed = discord.Embed(title=f"Warnings of {member.display_name}", description=f"{len(fetched)} warning(s)", color=0xff0000)
        if not fetched:
            embed.add_field(name="No Warnings Found", value="\u200b")
        for warning in fetched:
            embed.add_field(name=f"ID: {warning['__id']}", value=f"**Issuer:** <@!{warning['issuer']}>\n**Reason:** {warning['reason']}", inline=False)
        await ctx.send(embed=embed)
        db.close()

    async def createMuteRole(self, guild: discord.Guild):
        db = UnQLite("FHDatabase.db")
        roles = db.collection("Roles")
        fetched = roles.filter(lambda obj: obj["name"] == "muted")[0]["id"]
        muted_role = guild.get_role(fetched)
        if not muted_role:
            # Return None to inform that an invalid role has been given
            return None
        return muted_role

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member, *, reason: typing.Optional[str]):
        await add_to_logs(ctx.message.content, ctx.author)
        muted_role = await self.createMuteRole(ctx.guild)
        if not muted_role:
            await ctx.send("Error: An invalid role has been specified in the bot settings.")
            return
        # Move the role's position right below the bot's top role, if it's not already there
        role_position = ctx.guild.me.roles[-1].position - 1
        if muted_role.position != role_position:
            try:
                await muted_role.edit(position=role_position)
            except:
                await ctx.send("Error: The mute role is above my top role.")
        # Add the created role to the muted member
        await member.add_roles(muted_role, reason=reason)
        # Open mutes database
        db = UnQLite("FHDatabase.db")
        mutes = db.collection("Mutes")
        time = None
        if reason:
            possible_time = reason.split()[0]
            matches = re.match(r"(\d+[dhm])+", possible_time)
            if matches:
                time = matches.group(0)
                if len(reason.split()) > 1:
                    reason = ' '.join(reason.split()[1:])
                else:
                    reason = None
        # If time was specified, go for the timed unmute
        if time:
            delta = await convertTime(time)
            if not delta:
                mutes.store({"id": member.id, "time": None})
            else:
                date = datetime.datetime.utcnow() + delta
                mutes.store({"id": member.id, "time": date.strftime("%d %m %Y %H:%M:%S")})
            embed = discord.Embed(title="Member muted", description=f"{member.mention} was muted until {date.strftime('%B %d, %Y, %H:%M UTC.')}", color=0xc0c0c0)
        else:
            mutes.store({"id": member.id, "time": None})
            embed = discord.Embed(title="Member muted", description=f"{member.mention} was muted.")
        embed.add_field(name="Reason specified", value=reason)
        await ctx.send(embed=embed)
        try:
            embed = discord.Embed(title="You were muted", description=f"You were muted on Furry Hangout.", color=0xff0000)
            embed.add_field(name="Time specified", value=time)
            embed.add_field(name="Reason specified", value=reason)
            await member.send(embed=embed)
        except:
            print("Unable to DM the muted member")
        db.close()

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member):
        await add_to_logs(ctx.message.content, ctx.author)
        db = UnQLite("FHDatabase.db")
        mutes = db.collection("Mutes")
        roles = db.collection("Roles")
        fetched = roles.filter(lambda obj: obj["name"] == "muted")[0]["id"]
        muted_role = ctx.guild.get_role(fetched)
        if muted_role:
            if muted_role in member.roles:
                await member.remove_roles(muted_role)
        else:
            await ctx.send("Error: An invalid role is specified. If the member is muted, please manually unmute them.")
        fetched = mutes.filter(lambda obj: obj["id"] == member.id)
        if fetched:
            mutes.delete(fetched[0]["__id"])
        await ctx.send(f"{member.display_name} was unmuted.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: typing.Union[int, str], *, member: typing.Optional[discord.Member]):
        await add_to_logs(ctx.message.content, ctx.author)
        messages = []
        messages_to_delete = 0;
        if amount == "all":
            messages_to_delete = 500
        else:
            messages_to_delete = amount
        count = 0
        firstMessageChecked = False
        async for message in ctx.channel.history(limit=501, oldest_first=False):
            if not firstMessageChecked:
                firstMessageChecked = True
            else:
                if member is not None:
                    if message.author == member:
                        messages.append(message)
                        count += 1
                else:
                    messages.append(message)
                    count += 1
                if count == messages_to_delete:
                    break
        await ctx.channel.delete_messages(messages)
        print(f"{amount} messages deleted in #{ctx.channel.name}")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def message(self, ctx, member: discord.Member, *, message: str):
        await add_to_logs(ctx.message.content, ctx.author)
        signature = "I'm a bot and I was only asked to deliver this message. Replying to me will not get a response."
        try:
            await member.send(f"{message}\n\n{signature}")
            await ctx.send(f"Message successfully delivered to {member}!")
        except:
            print(f"Can't send a message to {member}")
            await member.send(f"Unable to send a message to {member}. :( Maybe they blocked me or have DMs turned off.")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def testwelcome(self, ctx):
        await add_to_logs(ctx.message.content, ctx.author)
        # For testing the welcoming image
        message, imageFile, location = await create_welcome(ctx.author, ctx.guild.member_count)
        await ctx.send(message, file=imageFile)
        os.remove(location)

# VOICE CHANNEL COMMANDS
class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx):
        await add_to_logs(ctx.message.content, ctx.author)
        # Save the command issuer's voice state
        voicestate = ctx.author.voice
        # Check if the bot is already connected somewhere
        if len(bot.voice_clients) > 0:
            botchannel = bot.voice_clients[0].channel
            # Check if the bot is currently on VC with others or is still playing something
            if len(botchannel.members) > 1 or bot.voice_clients[0].is_playing():
                await ctx.send(f"I'm currently occupied on {botchannel}.")
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

    @commands.command()
    async def leave(self, ctx):
        await add_to_logs(ctx.message.content, ctx.author)
        botchannel = bot.voice_clients[0].channel
        # Check that the command issuer is on the voice channel before disconnecting
        if await isOnChannel(ctx.author, botchannel):
            bot.voice_clients[0].stop()
            await bot.voice_clients[0].disconnect()

    @commands.command()
    async def play(ctx, *, search: str):
        await add_to_logs(ctx.message.content, ctx.author)
        print("Playing...")
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

# UTILITY COMMANDS
class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def remindme(self, ctx, in_or_at: str, time: str, remindertype: str, *, reminder: str):
        await add_to_logs(ctx.message.content, ctx.author)
        if remindertype != "once" and remindertype != "repeat":
            await ctx.send("Error in parameter: repeat")
            return
        date = await get_reminder_date(in_or_at, time)
        if type(date) is type("string"):
            await ctx.send(date)
            return
        # Interval is either the time specified with "in" (in minutes) or 1 day (1440 minutes) with "at"
        if in_or_at == "in":
            delta = await convertTime(time)
            interval = int(delta.total_seconds() / 60)
        else:
            interval = 1440
        db = UnQLite("FHDatabase.db")
        reminders = db.collection("Reminders")
        # remind parameter: "me" or "group", repeat parameter: True if reminder type is "repeat"
        reminders.store({"id": ctx.author.id, "remind": "me", "repeat": remindertype == "repeat", "interval": interval, "time": date.strftime("%d %m %Y %H:%M:%S"), "reminder": reminder})
        responses = ["Of course!", "Sure!", "Definitely!", "Absolutely!", "No problem!"]
        if remindertype == "once":
            willRepeat = "The reminder will be shown only once."
        else:
            willRepeat = "The reminder will be repeated after."
        await ctx.send(f"{random.choice(responses)} I will remind you at {date.strftime('%B %d, %H:%M UTC')} about: {reminder}\n{willRepeat}")
        db.close()

    @commands.command()
    async def remindgroup(self, ctx, in_or_at: str, time: str, remindertype: str, *, reminder: str):
        await add_to_logs(ctx.message.content, ctx.author)
        if remindertype != "once" and remindertype != "repeat":
            await ctx.send("Error in parameter: repeat")
            return
        date = await get_reminder_date(in_or_at, time)
        if type(date) is type("string"):
            await ctx.send(date)
            return
        responses = ["Of course!", "Sure!", "Definitely!", "Absolutely!", "No problem!"]
        if remindertype == "once":
            willRepeat = "The reminder will be shown only once."
        else:
            willRepeat = "The reminder will be repeated multiple times."
        bot_message = await ctx.send(f"{random.choice(responses)} I will send a reminder at {date.strftime('%B %d, %H:%M UTC')} about: {reminder}\nOpt in by reacting 👍 to this message.\n{willRepeat}")
        await bot_message.add_reaction("👍")
        # Interval is either the time specified with "in" (in minutes) or 1 day (1440 minutes) with "at"
        if in_or_at == "in":
            delta = await convertTime(time)
            interval = int(delta.total_seconds() / 60)
        else:
            interval = 1440
        db = UnQLite("FHDatabase.db")
        reminders = db.collection("Reminders")
        reminders.store({"id": bot_message.id, "channel": ctx.channel.id, "remind": "group", "repeat": remindertype == "repeat", "interval": interval, "time": date.strftime("%d %m %Y %H:%M:%S"), "reminder": reminder})
        db.close()

    @commands.command()
    async def reminders(self, ctx):
        await add_to_logs(ctx.message.content, ctx.author)
        db = UnQLite("FHDatabase.db")
        reminders = db.collection("Reminders")
        embed = discord.Embed(title=f"Reminders of {ctx.author}")
        fetched = reminders.filter(lambda obj: obj["id"] == ctx.author.id and obj["remind"] == "me")
        if not fetched:
            embed.description = "No reminders found. Create a new reminder using the `remindme` command"
        for reminder in fetched:
            date = datetime.datetime.strptime(reminder["time"], "%d %m %Y %H:%M:%S")
            embed.add_field(name=f"ID: {reminder['__id']}", value=f"**Content:** {reminder['reminder']}\n**Due:** {date.strftime('%B %-d %Y, %H:%M:%S UTC')}\n**Will Repeat:** {reminder['repeat']}")
        await ctx.send(embed=embed)
        db.close()

    @commands.command()
    async def forget(self, ctx, reminder_id: int):
        await add_to_logs(ctx.message.content, ctx.author)
        db = UnQLite("FHDatabase.db")
        reminders = db.collection("Reminders")
        fetched = reminders.filter(lambda obj: obj["id"] == ctx.author.id and obj["remind"] == "me" and obj["__id"] == reminder_id)
        if not fetched:
            await ctx.send(f"You have no reminders with ID {reminder_id}. Check your reminder IDs with `reminders`")
        else:
            bot_message = await ctx.send(f'Are you sure you want me to forget `{fetched[0]["reminder"]}`?')
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
                # if approved, inform that the reminder was deleted and proceed to remove it from the database, otherwise do nothing
                if reaction.emoji == "✅":
                    await bot_message.edit(content=f'I have forgotten {fetched[0]["reminder"]}.')
                    await bot_message.clear_reactions()
                    reminders.delete(reminder_id)
                elif reaction.emoji == "❌":
                    await bot_message.delete()
            db.close()

    @commands.command()
    async def forgetall(self, ctx):
        await add_to_logs(ctx.message.content, ctx.author)
        db = UnQLite("FHDatabase.db")
        reminders = db.collection("Reminders")
        fetched = reminders.filter(lambda obj: obj["id"] == ctx.author.id and obj["remind"] == "me")
        if not fetched:
            await ctx.send(f"You have no reminders to remove. Create a new reminder with the `remindme` command.")
        else:
            bot_message = await ctx.send(f'Are you sure you want me to forget all of your reminders?')
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
                # if approved, inform that the reminders were deleted and proceed to remove them from the database, otherwise do nothing
                if reaction.emoji == "✅":
                    await bot_message.edit(content=f'I have forgotten all of your reminders.')
                    await bot_message.clear_reactions()
                    for reminder in fetched:
                        reminders.delete(reminder["__id"])
                elif reaction.emoji == "❌":
                    await bot_message.delete()
            db.close()

    @commands.command()
    async def feedback(self, ctx, *, message: str):
        if ctx.channel.type == discord.ChannelType.private:
            staff_members = []
            staff_role = bot.get_guild(223340988314157056).get_role(225004317596319746)
            numbers = "0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟".split()
            embed = discord.Embed(title="Who to send it to?", description="React with the corresponding emoji.")
            embed.add_field(name="**ALL**", value="Emoji: 🅰️")
            index = 0
            async for member in bot.get_guild(223340988314157056).fetch_members():
                if index == 10:
                    break
                if staff_role in member.roles:
                    staff_members.append(member)
                    embed.add_field(name=f"**{member}**", value=f"Emoji: {numbers[index]}")
                    index += 1
            bot_message = await ctx.send(embed=embed)
            await bot_message.add_reaction("🅰️")
            for index in range(len(staff_members)):
                await bot_message.add_reaction(numbers[index])
            def check_reaction(reaction, user):
                return (reaction.emoji in numbers or reaction.emoji == "🅰️") and user == ctx.author
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check_reaction)
            except asyncio.TimeoutError:
                await bot_message.edit(content="Timed Out. Please resend the command.", embed=None)
            else:
                messages = []
                recipients = []
                def check_spam(reaction, user):
                    return reaction.emoji == "🚩" and reaction.message in messages and user in recipients
                embed = discord.Embed(title="Feedback received", description=f"Anonymous user has sent feedback.")
                embed.add_field(name="**Feedback**", value=message)
                if reaction.emoji == "🅰️":
                    embed.add_field(name="**Scope**", value="This feedback was sent to all staff members.", inline=False)
                    embed.add_field(name="Is this message spam?", value="Flag it by reacting with 🚩 within 1 hour and report to Veloxization#0735.")
                    sent_to = len(staff_members)
                    for member in staff_members:
                        try:
                            feedback_message = await member.send(embed=embed)
                            messages.append(feedback_message)
                            recipients.append(member)
                        except:
                            print(f"Unable to send feedback to {member}")
                            sent_to -= 1
                    await bot_message.edit(content=f"Feedback delivered to {sent_to} staff members!", embed=None)
                    try:
                        reaction, user = await bot.wait_for('reaction_add', timeout=3600.0, check=check_spam)
                    except asyncio.TimeoutError:
                        print("Feedback not reported as spam.")
                    else:
                        await add_to_logs(ctx.message.clean_content, ctx.author)
                else:
                    embed.add_field(name="**Scope**", value="This feedback was sent to you personally.", inline=False)
                    embed.add_field(name="Is this message spam?", value="Flag it by reacting with 🚩 within 1 hour and report to Veloxization#0735.")
                    index = numbers.index(reaction.emoji)
                    try:
                        feedback_message = await staff_members[index].send(embed=embed)
                    except:
                        await bot_message.edit(content=f"I was unable to deliver the feedback to {staff_members[index]}. :(", embed=None)
                    else:
                        await bot_message.edit(content=f"Feedback successfully delivered to {staff_members[index]}!", embed=None)
                        messages.append(feedback_message)
                        recipients.append(staff_members[index])
                        try:
                            reaction, user = await bot.wait_for('reaction_add', timeout=3600.0, check=check_spam)
                        except asyncio.TimeoutError:
                            print("Feedback not reported as spam.")
                        else:
                            await add_to_logs(ctx.message.clean_content, ctx.author)
        else:
            await ctx.message.delete()
            bot_message = await ctx.send("This command is reserved only for private messages! Please message me privately to use this command.")
            await bot_message.delete(delay=10.0)

# INFO COMMANDS
class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def stats(self, ctx, member: typing.Optional[discord.Member], channel: typing.Optional[discord.TextChannel]):
        await add_to_logs(ctx.message.content, ctx.author)
        # Default to command issuer in the current channel
        if member is None:
            member = ctx.author
        if channel is None:
            channel = ctx.message.channel
        if member.bot:
            await ctx.send("I can't do this for bots. :c")
            return
        # Inform that the bot is calculating the statistics
        botmessage = await ctx.send("Calculating...")
        # Put all the messages in a list
        messages = await channel.history(limit=500, oldest_first=False).flatten()
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
        # If the member doesn't have any messages in the specified channel, inform about it
        if user_messages == 0:
            averageLength = 0
            embed = discord.Embed(title=f"None of the past 500 messages in {channel.mention} were from {member.name}.")
        # Otherwise show the stats
        else:
            averageLength = round(combinedLength / user_messages, 2)
            embed = discord.Embed(title=f"Statistics for {member.name}", description=f"Analyzed {user_messages} messages in {channel.mention}", color=0x0ffca9)
            embed.add_field(name="Average message length", value=f"{averageLength} characters")
            embed.add_field(name="Total attachments", value=f"{totalAttachments} attachments")
        await botmessage.edit(content=None, embed=embed)

    @commands.command()
    async def userinfo(self, ctx, *, member: typing.Optional[discord.Member]):
        await add_to_logs(ctx.message.content, ctx.author)
        if member is None:
            member = ctx.author
        embed = discord.Embed(title=f"{member.name}'s info", color=member.color)
        embed.set_thumbnail(url=member.avatar_url)
        embed.add_field(name="Joined", value=member.joined_at.strftime("%B %d, %Y at %H:%M UTC"), inline=False)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%B %d, %Y at %H:%M UTC"), inline=False)
        db = UnQLite("FHDatabase.db")
        usernames = db.collection("Usernames")
        fetched = usernames.filter(lambda obj: obj["id"] == member.id)
        usernames = ""
        for row in fetched:
            usernames += row["username"] + ", "
        if usernames == "":
            usernames = "N/A"
        else:
            usernames = usernames[:-2]
        embed.add_field(name="Previous usernames", value=usernames, inline=False)
        nicknames = db.collection("Nicknames")
        fetched = nicknames.filter(lambda obj: obj["id"] == member.id)
        nicknames = ""
        for row in fetched:
            nicknames += row["nickname"] + ", "
        if nicknames == "":
            nicknames = "N/A"
        else:
            nicknames = nicknames[:-2]
        embed.add_field(name="Previous nicknames", value=nicknames, inline=False)
        db.close()

        roles = ""
        for role in member.roles:
            if role.name != "@everyone":
                roles = roles + role.mention + ", "
        if roles == "":
            roles = "None"
        else:
            roles = roles[:-2]
        embed.add_field(name="Roles", value=roles, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        await add_to_logs(ctx.message.content, ctx.author)
        embed = discord.Embed(title="Furry Hangout", description="Server info", color=0x8eff00)
        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.add_field(name="ID", value=ctx.guild.id, inline=True)
        embed.add_field(name="Owner", value=f"{ctx.guild.owner}", inline=True)
        embed.add_field(name="Members", value=f"{ctx.guild.member_count}", inline=True)
        embed.add_field(name="Text Channels", value=f"{len(ctx.guild.text_channels)}", inline=True)
        embed.add_field(name="Voice Channels", value=f"{len(ctx.guild.voice_channels)}", inline=True)
        embed.add_field(name="Creation Date", value=ctx.guild.created_at.strftime("%b %d, %Y, %H:%M:%S UTC"), inline=True)
        embed.add_field(name="Roles", value=f"{len(ctx.guild.roles) - 1}", inline=True)
        await ctx.send(embed=embed)

# FUN COMMANDS
class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def eightball(self, ctx, arg: typing.Optional[str]):
        await add_to_logs(ctx.message.content, ctx.author)
        with open('json/8ball.json') as json_data:
            responses = json.load(json_data)
            response = random.choice(responses)
            await ctx.send(response)

# HELP COMMANDS
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Command for listing all available commands and their function
    @commands.command()
    async def help(self, ctx, arg: str = "help"):
        await add_to_logs(ctx.message.content, ctx.author)
        description = "<required> [optional]" #To avoid continuous copy-pasting
        # List all moderator commands
        if arg.lower() == "mod":
            embed = discord.Embed(title="Moderator commands", description=description, color=0x7f00ff)
            embed.add_field(name="kick <@member> [reason]", value="Kicks a member with an optional reason.", inline=False)
            embed.add_field(name='ban <@member/ID> [days of messages deleted (max 7, default 0)] [reason]', value="Bans a user by ID or tag with optional amount of messages deleted and reason.", inline=False)
            embed.add_field(name="unban <ID> [reason]", value="Unbans a user by ID.", inline=False)
            embed.add_field(name="warn <@member> <reason>", value="Warns a member with given reason.", inline=False)
            embed.add_field(name="warnings <@member>", value="Lists the warnings of a member.", inline=False)
            embed.add_field(name="removewarn <ID>", value="Removes a warning with the given ID number.", inline=False)
            embed.add_field(name="mute <@member> [time] [reason]", value="Mutes a member from chatting and voice chatting with optional time and reason. Time units are m, h and d. Don't use spaces when specifying time. E.g. `mute @john 2d5h15m Spamming in #general`", inline=False)
            embed.add_field(name="unmute <@member>", value="Unmutes a specified member, given that they're muted.")
            embed.add_field(name="purge <amount> [@member]", value="Bulk deletes a specified amount of messages (max 500) from a channel. Optionally can be filtered to delete only a specified member's messages. E.g. `purge all @john` or `purge 10`", inline=False)
            embed.add_field(name="message <@member> <message>", value="I will deliver a message to the member of your choosing.", inline=False)
            embed.add_field(name="testwelcome", value="Displays the welcoming message as if a new member joined.", inline=False)
            await ctx.send(embed=embed)
        # Lists all music commands
        elif arg.lower() == "music":
            embed = discord.Embed(title="Music commands (UPCOMING, NON-FUNCTIONAL!)", description=description, color=0x208afc)
            embed.add_field(name="join", value="Makes the bot join your voice channel.", inline=False)
            embed.add_field(name="leave", value="Makes the bot leave the current voice channel.", inline=False)
            embed.add_field(name="play <URL>", value="Plays a song from a YouTube URL.", inline=False)
            embed.add_field(name="search <search term>", value="Searches a song from YouTube to play. Can be played by reacting with a corresponding number.", inline=False)
            await ctx.send(embed=embed)
        # Lists all utility commands
        elif arg.lower() == "utility":
            embed = discord.Embed(title="Utility commands", description=description, color=0xa4b4bc)
            embed.add_field(name="remindme <in/at> <time> <once/repeat> <reminder>", value="Sends you a reminder after a specified time. Don't use spaces when defining time. E.g. `remindme in 1d12h once Draw a new server icon.` (accepted time units: `d`, `h` and `m`) for a reminder in 36 hours or `remindme at 01:00PM repeat Eat lunch.` for a reminder that's repeated every day at 13:00 UTC (accepts both 24-hour and 12-hour formats). Remember to have your DMs enabled.", inline=False)
            embed.add_field(name="remindgroup <in/at> <time> <once/repeat> <reminder>", value="Sets a reminder for a group of people. Opt in by reacting to the message with 👍. Reminder will be automatically deleted if there are no reactions at activation time. Same format as `remindme`.", inline=False)
            embed.add_field(name="reminders", value="Lists all your active `remindme` reminders.", inline=False)
            embed.add_field(name="forget <ID>", value="Removes a personal reminder of the specified ID from you. IDs can be checked with the `reminders` command.", inline=False)
            embed.add_field(name="forgetall", value="Removes all your personal reminders.", inline=False)
            embed.add_field(name="feedback <message>", value="Sends feedback to all staff members or a staff member of your choice. The recipient will be confirmed before sending. Can only be used through direct messages to the bot.", inline=False)
            await ctx.send(embed=embed)
        elif arg.lower() == "fun":
            embed = discord.Embed(title="Fun commands", description=description, color=0xfc88c6)
            embed.add_field(name="eightball", value="The Magic 8 Ball answers a yes-no question for you")
            await ctx.send(embed=embed)
        # Lists all information commands
        elif arg.lower() == "info":
            embed = discord.Embed(title="Info commands", description="<required> [optional]", color=0x0ffca9)
            embed.add_field(name="stats [@member] [#channel]", value="Shows statistics of the past 500 messages in the selected channel, like average length. Defaults to yourself and the current channel.", inline=False)
            embed.add_field(name="userinfo [@member]", value="Shows user info, like join date, account creation date, previously seen usernames and nicknames... Defaults to yourself.", inline=False)
            embed.add_field(name="serverinfo", value="Shows Furry Hangout's information.")
            await ctx.send(embed=embed)
        elif arg.lower() == "help":
            await ctx.send("Usage: help <category>\n__**Categories**__\n**Mod**: Moderator commands\n**Music**: Music commands\n**Utility**: Utility commands, like the reminder command\n**Fun**: Commands just for fun!\n**Info**: Information about the guild and its members")

async def statusChanger():
    while True:
        with open('json/status.json') as json_data:
            activities = json.load(json_data)
            activity = discord.Activity(name=random.choice(activities), type=discord.ActivityType.competing)
        await bot.change_presence(activity=activity)
        await timer()
        await asyncio.sleep(20)

async def timer():
    # Check for reminders
    db = UnQLite("FHDatabase.db")
    reminders = db.collection("Reminders")
    for reminder in reminders.all():
        delta = datetime.datetime.strptime(reminder["time"], "%d %m %Y %H:%M:%S") - datetime.datetime.utcnow()
        if delta.total_seconds() <= 0:
            if reminder["remind"] == "me":
                embed = discord.Embed(title="REMINDER", description=f"{reminder['reminder']}")
                if reminder["repeat"]:
                    embed.add_field(name="Want to opt out?", value=f"You can opt out of this reminder using the command `forget {reminder['__id']}`.")
                try:
                    member = bot.get_user(reminder["id"])
                    await member.send(content="I am here with your reminder!", embed=embed)
                except:
                    print("Unable to send reminder, deleting reminder.")
                    reminders.delete(reminder["__id"])
                    return
                if reminder["repeat"]:
                    date = datetime.datetime.strptime(reminder["time"], "%d %m %Y %H:%M:%S") + datetime.timedelta(minutes=reminder["interval"])
                    reminders.update(reminder["__id"], {"id": reminder["id"], "remind": "me", "repeat": True, "interval": reminder["interval"], "time": date.strftime("%d %m %Y %H:%M:%S"), "reminder": reminder["reminder"]})
                else:
                    reminders.delete(reminder["__id"])
            else:
                try:
                    channel = bot.get_guild(223340988314157056).get_channel(reminder["channel"])
                    message = await channel.fetch_message(reminder["id"])
                except:
                    print("Couldn't access either the channel or the message. Deleting reminder.")
                    reminders.delete(reminder["__id"])
                    return
                for react in message.reactions:
                    # Save time by ignoring emojis other than the required one
                    if react.emoji != "👍":
                        continue
                    if react.emoji == "👍" and react.count <= 1:
                        embed = discord.Embed(title="Reminder Deleted", description=f"[This Reminder]({message.jump_url}) was deleted due to lack of participation.")
                        await channel.send(embed=embed)
                        reminders.delete(reminder["__id"])
                        return
                    users = await react.users().flatten()
                    for user in users:
                        if not user.bot and react.emoji == "👍":
                            embed = discord.Embed(title="REMINDER", description=f"{reminder['reminder']}")
                            if reminder["repeat"]:
                                embed.add_field(name="Want to opt out?", value=f"Remove your reaction from [This Message]({message.jump_url})")
                            try:
                                await user.send(content="I am here with your reminder!", embed=embed)
                            except:
                                print(f"Unable to send reminder to user {user}")
                    embed = discord.Embed(title="Reminder Sent to Users", description=f"[This Reminder]({message.jump_url}) has been sent out to users who reacted to the message.")
                    await channel.send(embed=embed)
                if reminder["repeat"]:
                    date = datetime.datetime.strptime(reminder["time"], "%d %m %Y %H:%M:%S") + datetime.timedelta(minutes=reminder["interval"])
                    reminders.update(reminder["__id"], {"id": reminder["id"], "channel": reminder["channel"], "remind": "group", "repeat": True, "interval": reminder["interval"], "time": date.strftime("%d %m %Y %H:%M:%S"), "reminder": reminder["reminder"]})
                else:
                    reminders.delete(reminder["__id"])
    # Check for expired mutes
    mutes = db.collection("Mutes")
    for mute in mutes.all():
        if mute["time"]:
            delta = datetime.datetime.strptime(mute["time"], "%d %m %Y %H:%M:%S") - datetime.datetime.utcnow()
            if delta.total_seconds() <= 0:
                roles = db.collection("Roles")
                fetched = roles.filter(lambda obj: obj["name"] == "muted")[0]["id"]
                muted_role = bot.get_guild(223340988314157056).get_role(fetched)
                member = bot.get_guild(223340988314157056).get_member(mute["id"])
                if muted_role in member.roles:
                    await member.remove_roles(muted_role)
                mutes.delete(mute["__id"])
    # Check for members to warn about kicks and to kick
    new_members = db.collection("NewMembers")
    for new_member in new_members.all():
        member = bot.get_guild(223340988314157056).get_member(new_member["id"])
        roles = db.collection("Roles")
        fetched = roles.filter(lambda obj: obj["name"] == "read_the_rules")[0]["id"]
        new_member_role = bot.get_guild(223340988314157056).get_role(fetched)
        if not (new_member_role in member.roles):
            new_members.delete(new_member["__id"])
            continue
        delta = datetime.datetime.utcnow() - member.joined_at
        if delta.days == 6 and not new_member["warned"]:
            new_members.update(new_member["__id"], {'id': member.id, 'member_number': new_member["member_number"], 'warned': True})
            try:
                await member.send("Hello! Six days ago you joined Furry Hangout but to my knowledge, you haven't read the rules yet. Be sure to do it within 24 hours (channel: #rules-and-info) and confirm in #rule-confirmation or you will be kicked for failure to go through rule confirmation!")
                print(f"Sent reminder of rule confirmation to {member.name}#{member.discriminator}")
            except:
                print(f"Couldn't send an inactivity warning to {member.name}#{member.discriminator}")
        elif delta.days == 7:
            try:
                await member.send("You have been kicked from Furry Hangout for failure to go through rule confirmation.")
            except:
                print(f"Couldn't send a kick message to {member}")
            global G_logChannel
            embed = discord.Embed(title="Member kicked for inactivity", description=f"{member.mention} was kicked for failure to go through rule confirmation.", color=0xff7f00)
            embed.set_author(name=member, icon_url=member.avatar_url)
            await G_logChannel.send(embed=embed)
            await member.kick(reason="Failure to go through rule confirmation within 7 days.")
    db.close()

async def get_reminder_date(in_or_at: str, time: str):
    timeNow = datetime.datetime.utcnow()
    if in_or_at != "in" and in_or_at != "at":
        return "Error in parameter: in or at"
    if in_or_at == "in":
        delta = await convertTime(time)
        if delta is None:
            return "Error in parameter: time (did you use the correct formatting?)"
        date = timeNow + delta
    elif in_or_at == "at":
        date_string = timeNow.strftime("%d-%m-%Y ") + time
        if "AM" in time.upper() or "PM" in time.upper():
            try:
                date = datetime.datetime.strptime(date_string.upper(), "%d-%m-%Y %I:%M%p")
            except:
                try:
                    date = datetime.datetime.strptime(date_string.upper(), "%d-%m-%Y %-I:%M%p")
                except:
                    return "Error in parameter: time (did you use the correct formatting?)"
        else:
            try:
                date = datetime.datetime.strptime(date_string, "%d-%m-%Y %H:%M")
            except:
                try:
                    date = datetime.datetime.strptime(date_string, "%d-%m-%Y %-H:%M")
                except:
                    return "Error in parameter: time (did you use the correct formatting?)"
                    return
        delta = date - timeNow
        if delta.total_seconds() < 0:
            date = date + datetime.timedelta(days=1)
    return date

async def convertTime(time: str):
    regex_days = "\\d+d{1}"
    regex_hours = "\\d+h{1}"
    regex_minutes = "\\d+m{1}"
    days = None
    hours = None
    minutes = None
    pattern = re.compile(regex_days, re.IGNORECASE)
    match = pattern.search(time)
    if match:
        days = int(time[match.start():match.end()-1])
    pattern = re.compile(regex_hours, re.IGNORECASE)
    match = pattern.search(time)
    if match:
        hours = int(time[match.start():match.end()-1])
    pattern = re.compile(regex_minutes, re.IGNORECASE)
    match = pattern.search(time)
    if match:
        minutes = int(time[match.start():match.end()-1])
    # If no matches were found, there's something wrong with the time format, return None in this case
    if not days and not hours and not minutes:
        return None
    # timedelta does not accept non-zero values
    if not days:
        days = 0
    if not hours:
        hours = 0
    if not minutes:
        minutes = 0
    return datetime.timedelta(days=days, hours=hours, minutes=minutes)

async def add_to_logs(command: str, user: discord.User, ):
    filename = f"{datetime.datetime.utcnow().strftime('%Y-%m-%d')}.log"
    content = f"{datetime.datetime.utcnow().strftime('%H:%M:%S')} - {user} ({user.id}) used {command}\n\n"
    with open(f"logs/{filename}", "a") as text_file:
        text_file.write(content)


bot.run(TOKEN)
