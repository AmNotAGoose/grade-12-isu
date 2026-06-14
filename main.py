from bot import DiscordBotIntegration
from config import Config
from inference import Inference
from memory import Memory
from pipeline import Pipeline
from secret_retriever import get_secret
from traits import Traits


DATABASE_PATH = "data/memory.db"
TRAITS_PATH = "data/traits.json"


def main():
    groq_api_key = get_secret("GROQ_API_KEY")
    bot_owner_id = get_secret("BOT_OWNER_ID")
    discord_token = get_secret("DISCORD_TOKEN")

    if not (groq_api_key and bot_owner_id and discord_token):
        print("Please input the information in secrets.toml! Read the README.md if you are confused.")
        return

    inference = Inference(groq_api_key)
    memory = Memory(DATABASE_PATH)
    config = Config(DATABASE_PATH)
    traits = Traits(TRAITS_PATH)
    pipeline = Pipeline(memory, config, traits, inference)
    bot = DiscordBotIntegration(pipeline, config, bot_owner_id)

    try:
        bot.run(discord_token)
    finally:
        config.close()
        memory.close()


if __name__ == "__main__":
    main()
