import asyncio

import discord

from identity import MENTION_MARKER, NAME, SELF_MARKER


INACTIVITY_SECONDS = 2
CONSIDERATION_SECONDS = 300
CHANNEL_HISTORY_LIMIT = 40
BOT_MENTION_MARKER = MENTION_MARKER

HELP_TEXT = f"{NAME} is a conversational Discord bot that follows one selected channel, remembers useful details, and responds as a consistent character.\n\n>set_channel - select the current channel as the only channel {NAME} watches and load its recent history (if any!)\n>clear - clear the selected channel and all memory\n>consider_speak - immediately let {NAME} consider starting a message\n>help - show this command list"
STARTUP_MESSAGE = "bot is up. run `>help` anywhere I can see for commands."


class DiscordBotIntegration(discord.Client):
    def __init__(self, pipeline, config, owner_id):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(intents=intents)

        self.pipeline = pipeline
        self.config = config
        self.owner_id = int(owner_id)
        self.batch = []
        self.batch_channel = None
        self.inactivity_task = None
        self.consideration_task = None
        self.owner_notified = False

    async def on_ready(self):
        print("Logged in as " + str(self.user))

        if not self.owner_notified:
            try:
                owner = await self.fetch_user(self.owner_id)
                await owner.send(STARTUP_MESSAGE)
                self.owner_notified = True
            except Exception as error:
                print("Could not notify bot owner: " + str(error))

        if not self.consideration_task:
            self.consideration_task = asyncio.create_task(self.consider_speaking_periodically())

    async def on_message(self, message):
        if message.author.bot:
            return

        command = message.content.strip().lower()
        try:
            match command:
                case ">set_channel":
                    if message.guild is not None:
                        await message.delete()
                    await self.set_channel(message)
                    return
                case ">clear":
                    if message.guild is not None:
                        await message.delete()
                    await self.clear_channel(message)
                    return
                case ">consider_speak":
                    if message.guild is not None:
                        await message.delete()
                    if self.is_owner(message.author):
                        await self.consider_speaking()
                    return
                case ">help":
                    if message.guild is not None:
                        await message.delete()
                    if self.is_owner(message.author):
                        await message.author.send(HELP_TEXT)
                    return
        except Exception as error:
            print("Command failed: " + str(error))
            return
        if message.channel.id != self.config.get_channel_id():
            return

        data = self.message_data(message)
        self.batch.append(data)
        self.batch_channel = message.channel

        if data["addressed"]:
            await self.flush_batch()
            return
        self.reset_inactivity_timer()

    async def on_typing(self, channel, user, when):
        if user.bot:
            return
        if channel.id != self.config.get_channel_id():
            return
        if self.batch:
            self.reset_inactivity_timer()

    async def set_channel(self, message):
        if not self.is_owner(message.author):
            await message.author.send("only the bot owner can set the channel!")
            return

        if message.guild is None:
            await message.author.send("the tracked channel must be in a server")
            return

        permissions = message.channel.permissions_for(message.guild.me)
        if not permissions.view_channel or not permissions.send_messages or not permissions.read_message_history or not permissions.manage_messages:
            await message.author.send("i need View Channel, Send Messages, Read Message History, and Manage Messages in that channel")
            return

        self.config.set_channel_id(message.channel.id)
        self.config.set_guild(message.guild.name, message.guild.description)
        self.config.set_channel(message.channel.name, message.channel.topic)

        history = await self.channel_history(message)
        self.batch = []
        self.batch_channel = None

        print("Tracking channel " + str(message.channel.id))
        await message.author.send("i'll only watch that channel")

        if history:
            print("Loaded " + str(len(history)) + " previous messages")
            self.pipeline.ingest(history)

    async def clear_channel(self, message):
        if not self.is_owner(message.author):
            await message.author.send("only the bot owner can clear the channel")
            return

        if self.inactivity_task:
            self.inactivity_task.cancel()
        self.inactivity_task = None

        self.batch = []
        self.batch_channel = None

        self.config.clear_channel_selection()
        self.pipeline.memory.clear()
        self.pipeline.traits.reset_to_original()

        print("Cleared tracked channel and reset traits")
        await message.author.send("i cleared the tracked channel and memory")

    def is_owner(self, user):
        return user.id == self.owner_id

    async def channel_history(self, command_message):
        messages = []
        history = command_message.channel.history(
            limit=CHANNEL_HISTORY_LIMIT,
            before=command_message,
            oldest_first=False,
        )
        async for message in history:
            if message.author.bot:
                continue
            messages.append(self.message_data(message))
        messages.reverse()
        return messages

    def message_data(self, message):
        addressed = self.user and self.user in message.mentions
        mentions_others = any(
            not self.user or user.id != self.user.id
            for user in message.mentions
        )
        return {
            "author": message.author.display_name if message.author.id != self.user.id else SELF_MARKER,
            "content": self.replace_mentions(message),
            "timestamp": message.created_at.isoformat(),
            "addressed": bool(addressed),
            "mentions_others": mentions_others,
        }

    def replace_mentions(self, message):
        content = message.content
        for user in message.mentions:
            if self.user and user.id == self.user.id:
                replacement = BOT_MENTION_MARKER
            else:
                replacement = "@" + user.display_name
            content = content.replace("<@" + str(user.id) + ">", replacement)
            content = content.replace("<@!" + str(user.id) + ">", replacement)
        return content

    def reset_inactivity_timer(self):
        if self.inactivity_task:
            self.inactivity_task.cancel()
        self.inactivity_task = asyncio.create_task(self.flush_after_inactivity())

    async def flush_after_inactivity(self):
        try:
            await asyncio.sleep(INACTIVITY_SECONDS)
            self.inactivity_task = None
            await self.flush_batch()
        except asyncio.CancelledError:
            return

    async def flush_batch(self):
        if self.inactivity_task:
            self.inactivity_task.cancel()
        self.inactivity_task = None
        if not self.batch:
            return
        batch = self.batch
        channel = self.batch_channel
        self.batch = []
        self.batch_channel = None
        print("Processing batch of " + str(len(batch)) + " messages")

        reply = self.pipeline.process(batch)

        if reply:
            await channel.send(reply)
            print("Reply sent to channel " + str(channel.id))

    async def consider_speaking_periodically(self):
        while True:
            await asyncio.sleep(CONSIDERATION_SECONDS)
            await self.consider_speaking()

    async def consider_speaking(self):
        if self.batch:
            return
        channel_id = self.config.get_channel_id()
        if channel_id is None:
            return
        channel = self.get_channel(channel_id)
        if not channel:
            return
        print("Considering whether to speak")
        reply = self.pipeline.process([], consider_speaking=True)
        if reply:
            await channel.send(reply)
            print("Initiated message in channel " + str(channel.id))
