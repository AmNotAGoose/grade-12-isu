import tomllib
from pathlib import Path


SECRETS_PATH = Path(__file__).with_name("secrets.toml")


def get_secret(name):
    with open(SECRETS_PATH, "rb") as file:
        secrets = tomllib.load(file)
    return secrets.get(name)