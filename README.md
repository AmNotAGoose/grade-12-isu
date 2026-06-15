# Aaron
Aaron is a conversational Discord bot that follows one selected channel, remembers useful details, and responds in natural language as a consistent character.

## Features

- Decides when to speak naturally (no commands or triggers required)
- Responds instantly when directly mentioned
- Ignores messages directed at other users
- Sends unprompted messages every 5 minutes when it has something to say
- Batches messages before responding to read conversations as a whole
- Short term memory of recent messages persisted in SQLite
- Long term memory of facts extracted from older conversations
- Memory survives bot restarts
- Personality traits that shift gradually based on conversation tone
- Server and channel context injected into every response
- Multiple Groq model fallback for reliability
- Refusal detection with automatic model retry

# Commands (gets sent to bot owner in dms)
- `>set_channel` - select the current channel as the only channel Aaron watches and load its recent history (if any!)
- `>clear` - clear the selected channel and all memory
- `>consider_speak` - immediately let Aaron consider starting a message
- `>help` - show this command list

# How to install
1. Clone this repo
2. Create and activate a virtual environment.
3. Run `pip install -r requirements.txt`
4. Create a secrets.toml file in the root directory. See Getting Your Keys if you don't have these.
```toml
DISCORD_TOKEN = "your discord token here"
GROQ_API_KEY = "your groq api key here"
BOT_OWNER_ID = "your discord user id here"
```
5. Run `main.py`

## Getting Your Keys

### Groq API Key
1. Go to https://console.groq.com
2. Sign up for a free account
3. Navigate to API Keys in the left sidebar
4. Click Create API Key
5. Copy the key into secrets.toml as GROQ_API_KEY

### Discord Bot Token
1. Go to https://discord.com/developers/applications
2. Click New Application and give it a name
3. Go to the Bot tab on the left
4. Click Reset Token and copy it into secrets.toml as DISCORD_TOKEN
5. Scroll down and enable Message Content Intent under Privileged Gateway Intents
6. Go to OAuth2 in the left sidebar.
7. Copy ClientID 
8. Go to https://discordapi.com/permissions.html
9. Select Send Messages, Read Message History, View Channels, and Manage Messages
10. Paste your ClientID in the box
11. Click link and add to your server

### Bot Owner ID
1. Open Discord
2. Go to Settings -> Advanced
3. Enable Developer Mode
4. Right click your own username anywhere in Discord
5. Click Copy User ID
6. Paste it into secrets.toml as BOT_OWNER_ID
