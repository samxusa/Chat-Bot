"""Default starter list; group admins can customize terms in settings."""

DEFAULT_ABUSE_TERMS = [
    "madarchod", "mc", "behenchod", "bc", "bkl", "chutiya", "gaand",
    "harami", "fuck", "shit", "bitch", "asshole",
]


def contains_abuse(text: str, terms: list[str]) -> bool:
    import re
    normalized = " ".join(text.casefold().split())
    for term in terms:
        term = term.strip().casefold()
        if term and re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", normalized):
            return True
    return False
