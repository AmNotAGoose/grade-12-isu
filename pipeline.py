from datetime import datetime, timezone

from identity import MENTION_MARKER, NAME, SELF_MARKER
from promptbuilder import get_identity, get_prompt


ROUTING_RESULT_MARKER = "===ROUTING RESULT==="


class Pipeline:
    def __init__(self, memory, config, traits, inference, policy_path=None):
        self.memory = memory
        self.config = config
        self.traits = traits
        self.inference = inference
        self.policy_path = policy_path
        self.routing_reason = ""

    def should_reply(self, batch, consider_speaking=False): # CALL 1
        if not consider_speaking and any(item.get("addressed") for item in batch):
            self.routing_reason = f"{NAME} was directly mentioned."
            print("Reply decision: YES (directly addressed)")
            return True

        system = f"""Decide whether {NAME} should reply to the conversation. Do not write the reply.

Markers:
- {SELF_MARKER} is a previous message from {NAME}.
- {MENTION_MARKER} is a direct mention of {NAME}.

Priority:
1. First identify who the newest message is addressed to.
2. A question to an @mentioned person is about that person, not {NAME}.
3. Topic relevance or shared biography never changes the addressee.
4. Group invitations, greetings, and personal statements can invite {NAME} without mentioning him.

Examples:
- "wait @sam do you go to this school?" -> NO
- "@sam what do you think, and does anyone else have ideas?" -> YES
- "{SELF_MARKER}: that claim is wrong" then "alex: why?" -> YES
- "alex: i really wish other people would message here" -> YES
- "sam: brb, getting water" -> NO

Remember you are deciding if {NAME} should reply specifically.

Reason in one short line, then write:
{ROUTING_RESULT_MARKER}
YES or NO

{self.routing_character_context()}"""

        user = self.conversation_context(batch)
        if consider_speaking:
            user += f"\n\nCLASSIFICATION TASK: {NAME} is considering starting a message without being prompted. Choose YES only if the recent conversation gives {NAME} a natural, relevant reason to speak, such as an unfinished thought, useful follow-up, or fitting joke. Usually choose NO. Do not use unrelated long-term memory as a reason to speak. Briefly explain the routing factors, then provide the marked result in the required format."
        else:
            user += "\n\nCLASSIFICATION TASK: Do not answer the messages. Would the character naturally respond? Briefly explain the routing factors, then provide the marked result in the required format."

        response = self.inference.call(system, user, temperature=0)
        print("Routing response: " + repr(response))

        decision = self.routing_decision(response)
        self.routing_reason = self.result_reason(response, ROUTING_RESULT_MARKER)

        should_reply = decision == "YES"

        print(f"Reply decision: {decision or 'INVALID'}")

        return should_reply

    def routing_decision(self, response):
        if not isinstance(response, str):
            return ""

        text = response.strip()
        if text.upper() in ("YES", "NO"):
            return text.upper()
        if ROUTING_RESULT_MARKER not in text:
            return ""

        result = text.rsplit(ROUTING_RESULT_MARKER, 1)[1].strip().upper()
        return result if result in ("YES", "NO") else ""

    def result_reason(self, response, marker):
        if not isinstance(response, str) or marker not in response:
            return ""
        return response.rsplit(marker, 1)[0].strip()

    def reply_text(self, response):
        if not isinstance(response, str):
            return ""
        return response.strip()

    def update_traits(self, batch):  # CALL 2
        system = f"Evaluate whether this conversation provides strong evidence that a character trait should move to one adjacent level. Each level states when it applies and the resulting style and reasoning changes. Choose based primarily on the applicability conditions; use style and reasoning to understand the behavioral consequence. {MENTION_MARKER} only means the author directly mentioned {NAME}; use it to understand who is being addressed, but do not treat the marker itself as evidence for any trait. Never choose a level that is not shown."

        user = f"""
        
Available trait levels:
{self.traits.prompt_text()}

New messages:
{self.format_messages(batch)}

Reason briefly about whether the new messages satisfy each level's applicability conditions strongly enough for the trait to stay at its current level or move to the shown lower or higher level. A weak or isolated signal should not change a trait.

After reasoning, write this marker on its own line:
{self.traits.result_marker()}
Then write exactly one JSON object like {{"earnestness": 4}}. Keys must be shown trait names. Values must be the shown lower or higher integer. Omit unchanged traits. Use {{}} when no change is justified. Write nothing after the JSON."""

        response = self.inference.call(system, user)
        self.traits.apply_response(response)

    def get_reply(self, batch, consider_speaking=False): # CALL 3
        user = self.conversation_context(batch)
        user += f"""

Reason for replying:
{self.routing_reason or "No rationale was provided."}

Write {NAME}'s next Discord message.
- {SELF_MARKER} is {NAME}; every other author is someone else.
- Never take another speaker's facts as {NAME}'s facts.
- Never answer for an @mentioned person.
- Use memory only when it directly helps answer the current message.
- Do not invent personal facts.
- Return only the Discord message, with no reasoning, label, or marker."""
        if consider_speaking:
            user += f"\n{NAME} is initiating rather than replying. Write one natural message grounded in the recent conversation. Do not mention that {NAME} was waiting, checking in, or deciding whether to speak."
        response = self.inference.call(self.character_context(), user)
        print("Reply generation response: " + repr(response))
        return self.reply_text(response)

    def ingest(self, messages):
        self.memory.append_messages(messages)
        self.memory.process_overflow(self.inference.call)

    def process(self, batch, consider_speaking=False):
        if batch:
            self.ingest(batch)

        if not self.should_reply(batch, consider_speaking):
            return ""

        if batch:
            self.update_traits(batch)

        reply = self.get_reply(batch, consider_speaking)

        self.store_reply(reply)
        if reply:
            self.memory.process_overflow(self.inference.call)

        return reply

    def store_reply(self, reply):
        if not reply:
            return
        self.memory.append_messages([{
            "author": SELF_MARKER,
            "content": reply,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }])

    def character_context(self):
        return get_prompt(self.config) + f"\n\nCurrent trait policies:\nApply each active policy to both {NAME}'s writing style and {NAME}'s reasoning process. The style and reasoning lines are behavioral instructions, not cosmetic descriptions.\n\n" + "\n\n".join(self.traits.interpretations())

    def routing_character_context(self):
        return get_identity() + "\n\nCurrent trait policies:\n" + "\n\n".join(self.traits.interpretations())

    def conversation_context(self, batch):
        parts = [
            "Long-term memory:\n" + (self.memory.read_long_term() or "none"),
            "Conversation:\n" + (
                self.format_messages(self.conversation_messages(batch))
                or "none"
            ),
        ]
        return "\n\n".join(parts)

    def conversation_messages(self, batch):
        recent = self.memory.read_short_term()
        if not batch or self.messages_end_with(recent, batch):
            return recent
        return recent + batch

    def messages_end_with(self, messages, suffix):
        if len(messages) < len(suffix):
            return False
        return all(
            self.message_identity(left) == self.message_identity(right)
            for left, right in zip(messages[-len(suffix):], suffix)
        )

    def message_identity(self, message):
        return (
            message.get("author"),
            message.get("content"),
            message.get("timestamp"),
        )

    def format_messages(self, messages):
        lines = []
        for item in messages:
            author = item["author"]
            if author == "me":
                author = SELF_MARKER
            lines.append(author + ": " + item["content"])
        return "\n".join(lines)
