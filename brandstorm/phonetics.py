"""Phonetic matching helpers (Soundex) for the USPTO tier.

Used to flag live marks that sound like a candidate even when spelled
differently (e.g. SMITH vs SMYTH). Pure stdlib, no dependencies.
"""


def soundex(word: str) -> str:
    """Classic American Soundex. Returns a 4-character code (letter + 3 digits)."""
    word = "".join(ch for ch in word.upper() if ch.isalpha())
    if not word:
        return "0000"
    first = word[0]
    codes = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }
    prev = codes.get(first, "")
    digits = []
    for ch in word[1:]:
        code = codes.get(ch, "")
        if code and code != prev:
            digits.append(code)
        prev = code
    return (first + "".join(digits) + "000")[:4]


def phonetic_match(a: str, b: str) -> bool:
    """True when two strings share a Soundex code on their first token."""
    a_tok = a.split()[0] if a.split() else a
    b_tok = b.split()[0] if b.split() else b
    return soundex(a_tok) == soundex(b_tok) and a_tok.lower() != b_tok.lower()
