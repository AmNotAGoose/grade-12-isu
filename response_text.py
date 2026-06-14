def remove_code_block(text):
    """Remove code block."""
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    if not lines[0].strip().startswith("```"):
        return text
    if lines[-1].strip() != "```":
        return text
    return "\n".join(lines[1:-1]).strip()
