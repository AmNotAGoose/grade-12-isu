import json

from response_text import remove_code_block


RESULT_MARKER = "===RESULT BELOW==="


class Traits:
    def __init__(self, path):
        self.path = path

    def read(self):
        with open(self.path, "r", encoding="utf-8") as file:
            return json.load(file)

    def reset_to_original(self):
        data = self.read()

        original = data.get("original_traits")

        if not original:
            print("The original traits were not stored!")
            return

        data["traits"] = dict(original)

        self.write(data)
        print("Traits reset to original values.")

    def values(self):
        return self.read()["traits"]

    def result_marker(self):
        return RESULT_MARKER

    def interpretations(self):
        data = self.read()
        lines = []
        for name, value in data["traits"].items():
            definition = data["definitions"][name][str(value)]
            lines.append(self.interpretation(name, value, definition))
        return lines

    def interpretation(self, name, value, definition):
        return name + " level " + str(value) + ":\nstyle: " + definition["style"] + "\nreasoning: " + definition["reasoning"]

    def prompt_text(self):
        data = self.read()
        sections = []
        for name, value in data["traits"].items():
            sections.append(self.trait_prompt(data, name, value))
        return "\n\n".join(sections)

    def trait_prompt(self, data, name, value):
        definitions = data["definitions"][name]
        lines = [name + ":"]
        if value > 1:
            lines.append(self.format_trait_prompt_line("lower", value - 1, definitions[str(value - 1)]["applicable_when"]))
        lines.append(self.format_trait_prompt_line("current", value, definitions[str(value)]["applicable_when"]))
        if value < 5:
            lines.append(self.format_trait_prompt_line("higher", value + 1, definitions[str(value + 1)]["applicable_when"]))
        return "\n".join(lines)

    def format_trait_prompt_line(self, label, value, applicable_when):
        return label + " level " + str(value) + ":\n  applicable when: " + applicable_when

    def apply_response(self, response):
        changes = self.parse_response(response)
        if changes:
            self.update(changes)
            print("Traits updated: " + json.dumps(changes))
        return changes

    def parse_response(self, response):
        result = self.result_text(response)
        if not result:
            return {}
        try:
            changes = json.loads(result)
        except (TypeError, json.JSONDecodeError):
            return {}
        if not isinstance(changes, dict):
            return {}
        return self.valid_changes(changes)

    def result_text(self, response):
        if not isinstance(response, str) or RESULT_MARKER not in response:
            return ""
        result = response.rsplit(RESULT_MARKER, 1)[1].strip()
        return remove_code_block(result)

    def valid_changes(self, changes):
        current = self.values()
        valid = {}
        for name, value in changes.items():
            if name not in current or not isinstance(value, int):
                continue
            if abs(value - current[name]) == 1:
                valid[name] = value
        return valid

    def update(self, changes):
        data = self.read()
        for name, value in changes.items():
            if name not in data["traits"] or not isinstance(value, int):
                continue
            data["traits"][name] = max(1, min(5, value))
        self.write(data)

    def write(self, data):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
            file.write("\n")
