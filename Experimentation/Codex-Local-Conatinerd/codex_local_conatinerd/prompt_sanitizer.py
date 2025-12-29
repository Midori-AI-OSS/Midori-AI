def sanitize_prompt(prompt: str) -> str:
    replacements = {
        '"': "`",
        "“": "`",
        "”": "`",
        "„": "`",
        "‟": "`",
    }
    return "".join(replacements.get(ch, ch) for ch in (prompt or ""))
