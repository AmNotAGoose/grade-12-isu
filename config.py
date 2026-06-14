import sqlite3


class Config:
    def __init__(self, database_path):
        self.database_path = database_path
        self.connection = sqlite3.connect(database_path)
        self.create_table()

    def create_table(self):
        self.connection.execute("CREATE TABLE IF NOT EXISTS bot_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.connection.commit()

    def set_channel_id(self, channel_id):
        self.set_value("channel_id", channel_id)

    def set_guild(self, name, description):
        self.connection.executemany(
            "INSERT OR REPLACE INTO bot_settings (name, value) VALUES (?, ?)",
            [
                ("guild_name", str(name or "")),
                ("guild_description", str(description or "")),
            ],
        )
        self.connection.commit()

    def set_channel(self, name, description):
        self.connection.executemany(
            "INSERT OR REPLACE INTO bot_settings (name, value) VALUES (?, ?)",
            [
                ("channel_name", str(name or "")),
                ("channel_description", str(description or "")),
            ],
        )
        self.connection.commit()

    def get_channel_id(self):
        value = self.get_value("channel_id")
        return int(value) if value is not None else None

    def get_guild_name(self):
        return self.get_value("guild_name")

    def get_guild_description(self):
        return self.get_value("guild_description")

    def get_channel_name(self):
        return self.get_value("channel_name")

    def get_channel_description(self):
        return self.get_value("channel_description")

    def clear_channel_selection(self):
        self.connection.execute("DELETE FROM bot_settings WHERE name IN ('channel_id', 'guild_name', 'guild_description', 'channel_name', 'channel_description')")
        self.connection.commit()

    def set_value(self, name, value):
        self.connection.execute(
            "INSERT OR REPLACE INTO bot_settings (name, value) VALUES (?, ?)",
            (name, str(value)),
        )
        self.connection.commit()

    def get_value(self, name):
        row = self.connection.execute("SELECT value FROM bot_settings WHERE name = ?", (name,)).fetchone()
        return row[0] if row else None

    def close(self):
        self.connection.close()
