from pathlib import Path


DATA_DIR = Path(__file__).with_name("data")
IDENTITY_PATH = DATA_DIR / "identity.md"
POLICY_PATH = DATA_DIR / "policy.md"


def get_identity():
    with open(IDENTITY_PATH, "r", encoding="utf-8") as file:
        return file.read().strip()


def get_prompt(config=None):
    identity = get_identity()
    with open(POLICY_PATH, "r", encoding="utf-8") as file:
        policy = file.read().strip()
    text = identity + "\n\n" + policy

    if not config:
        return text

    guild_name = config.get_guild_name()
    guild_description = config.get_guild_description()
    if guild_name or guild_description:
        text += f"\n\n## Server Context\n\nServer name: {guild_name or 'unknown'}"
        if guild_description:
            text += f"\n\nServer description: {guild_description}"

    channel_name = config.get_channel_name()
    channel_description = config.get_channel_description()
    if channel_name or channel_description:
        text += f"\n\n## Channel Context\n\nChannel name: {channel_name or 'unknown'}"
        if channel_description:
            text += f"\n\nChannel description: {channel_description}"

    return text
