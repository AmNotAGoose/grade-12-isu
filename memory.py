import json
import re
import sqlite3

from identity import MENTION_MARKER, NAME
from response_text import remove_code_block


SHORT_TERM_SPILL_THRESHOLD = 30
SHORT_TERM_RETAINED = 20
LONG_TERM_LIMIT = 30
LONG_TERM_CONDENSED_LIMIT = 10
MEMORY_RESULT_MARKER = "===MEMORIES BELOW==="


class Memory:
    def __init__(self, database_path):
        self.database_path = database_path
        self.connection = sqlite3.connect(database_path)
        self.create_tables()

    def create_tables(self):
        self.connection.execute("CREATE TABLE IF NOT EXISTS short_term (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, content TEXT, timestamp TEXT)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS long_term (id INTEGER PRIMARY KEY AUTOINCREMENT, memory TEXT, timestamp TEXT)")
        self.connection.commit()

    def append_messages(self, messages):
        incoming = [
            (item["author"], item["content"], item["timestamp"])
            for item in messages
        ]
        if not incoming:
            return

        existing = self.connection.execute(
            "SELECT author, content, timestamp FROM short_term ORDER BY id"
        ).fetchall()
        rows = list(dict.fromkeys(existing + incoming))
        rows.sort(key=lambda row: row[2])

        with self.connection:
            self.connection.execute("DELETE FROM short_term")
            self.connection.executemany(
                "INSERT INTO short_term (author, content, timestamp) VALUES (?, ?, ?)",
                rows,
            )

    def read_short_term(self):
        rows = self.connection.execute("SELECT author, content, timestamp FROM short_term ORDER BY id DESC LIMIT 20").fetchall()
        rows.reverse()
        return [
            {"author": row[0], "content": row[1], "timestamp": row[2]}
            for row in rows
        ]

    def read_long_term(self):
        rows = self.connection.execute("SELECT memory FROM long_term ORDER BY id").fetchall()
        return "\n".join(row[0] for row in rows)

    def process_overflow(self, inference):
        self.spill_short_term(inference)
        self.condense_long_term(inference)

    def spill_short_term(self, inference):
        rows = self.overflow_rows()
        if not rows:
            return
        print("Processing " + str(len(rows)) + " short-term messages")
        prompt = f"Extract only durable facts worth remembering later. {MENTION_MARKER} marks a direct mention of {NAME}; it is not a person, fact, name, or memory, so never include it in an extracted memory. Each memory must be one standalone factual string. Use explicit subjects and preserve the exact relationships stated in the messages. Do not infer missing details, transfer dates between facts, or combine separate claims. Reason briefly, then write this marker on its own line: " + MEMORY_RESULT_MARKER + "\nAfter it, write only a JSON array of strings. Return [] when nothing is important enough to remember."
        response = inference(prompt, self.format_rows(rows))
        self.store_overflow(rows, self.parse_memories(response))

    def overflow_rows(self):
        count = self.connection.execute("SELECT COUNT(*) FROM short_term").fetchone()[0]
        if count <= SHORT_TERM_SPILL_THRESHOLD:
            return []
        overflow = count - SHORT_TERM_RETAINED
        return self.connection.execute("SELECT id, author, content, timestamp FROM short_term ORDER BY id LIMIT ?", (overflow,)).fetchall()

    def store_overflow(self, rows, memories):
        if memories:
            stored = [(memory, rows[-1][3]) for memory in memories]
            self.connection.executemany("INSERT INTO long_term (memory, timestamp) VALUES (?, ?)", stored)
            print("Stored " + str(len(memories)) + " long-term memories")
        else:
            print("No durable memories found")
        self.connection.execute("DELETE FROM short_term WHERE id <= ?", (rows[-1][0],))
        self.connection.commit()

    def condense_long_term(self, inference):
        rows = self.connection.execute("SELECT memory, timestamp FROM long_term ORDER BY id").fetchall()

        if len(rows) <= LONG_TERM_LIMIT:
            return

        prompt = "Condense these durable memories into at most " + str(LONG_TERM_CONDENSED_LIMIT) + f" standalone factual memories. {MENTION_MARKER} is a message-processing marker, not a fact or person; remove it rather than preserving it. Ignore duplicate entries. Merge related entries when their facts can be preserved clearly, but do not merge unrelated people or claims. Preserve explicit names, relationships, dates, and ownership of each fact. Use fewer than " + str(LONG_TERM_CONDENSED_LIMIT) + " memories when fewer are sufficient. Write this marker on its own line: " + MEMORY_RESULT_MARKER + "\nAfter it, write only a JSON array containing no more than " + str(LONG_TERM_CONDENSED_LIMIT) + " strings."

        response = inference(prompt, "\n".join(row[0] for row in rows))

        memories = self.unique_memories(self.parse_memories(response))
        if not memories or len(memories) > LONG_TERM_CONDENSED_LIMIT:
            return
        new_rows = [(memory, rows[-1][1]) for memory in memories]

        self.connection.execute("DELETE FROM long_term")
        self.connection.executemany("INSERT INTO long_term (memory, timestamp) VALUES (?, ?)", new_rows)
        self.connection.commit()

        print("Condensed " + str(len(rows)) + " long-term memories into " + str(len(memories)))

    def unique_memories(self, memories):
        unique = []
        seen = set()

        for memory in memories:
            key = memory.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(memory)

        return unique

    def parse_memories(self, response):
        result = self.memory_result(response)
        if not result:
            return []

        try:
            memories = json.loads(result)
        except (TypeError, json.JSONDecodeError):
            return []

        if not isinstance(memories, list):
            return []
        return [item.strip() for item in memories if isinstance(item, str) and item.strip()]

    def memory_result(self, response):
        if not isinstance(response, str):
            return ""

        marker = re.search(r"(?im)^[#=\s]*MEMORIES BELOW[#=\s]*$", response)

        if not marker:
            return ""

        result = response[marker.end():].strip()
        return remove_code_block(result)

    def format_rows(self, rows):
        return "\n".join(row[3] + " " + row[1] + ": " + row[2] for row in rows)

    def clear(self):
        self.connection.execute("DELETE FROM short_term")
        self.connection.execute("DELETE FROM long_term")
        self.connection.commit()

    def close(self):
        self.connection.close()
