import re

# Order matters: longer/more-specific patterns must come before shorter ones
KEYWORDS = [
    # --- Control flow ---
    ("warna_agar",  "elif"),
    ("agar",        "if"),
    ("warna",       "else"),
    ("jabtak",      "while"),
    ("ke_liye",     "for"),
    ("mein",        "in"),
    ("band_karo",   "break"),
    ("agla",        "continue"),
    ("pass_karo",   "pass"),

    # --- Functions & classes ---
    ("kaam",        "def"),
    ("wapas",       "return"),
    ("class",       "class"),
    ("khud",        "self"),

    # --- I/O ---
    ("dikhao",      "print"),
    ("lo",          "input"),

    # --- Variable declaration (strip keyword) ---
    ("banao",       ""),

    # --- Boolean / None ---
    ("sach",        "True"),
    ("jhooth",      "False"),
    ("kuch_nahi",   "None"),

    # --- Logic operators ---
    ("aur",         "and"),
    ("ya",          "or"),
    ("nahi",        "not"),

    # --- Exception handling ---
    ("koshish",     "try"),
    ("pakdo",       "except"),
    ("antim",       "finally"),
    ("uthao",       "raise"),

    # --- Imports ---
    ("laao",        "import"),
    ("se",          "from"),

    # --- Other builtins ---
    ("lambai",      "len"),
    ("prakar",      "type"),
    ("seema",       "range"),
    ("andaza",      "int"),
    ("dasha_mlav",  "float"),
    ("akshar",      "str"),
    ("suchi",       "list"),
    ("theli",       "dict"),
    ("samooh",      "set"),
]

KW_MAP = {h: p for h, p in KEYWORDS}
KW_SET = set(h for h, _ in KEYWORDS)
OPS_TWO = {"**", "//", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/="}


def translate(code):
    for hinglish, python in KEYWORDS:
        if python == "":
            code = re.sub(r'\b' + re.escape(hinglish) + r'\b\s*', python, code)
        else:
            code = re.sub(r'\b' + re.escape(hinglish) + r'\b', python, code)
    return code


def _tokenize_line(line):
    tokens = []
    s = line.lstrip()
    indent = len(line) - len(s)
    i = 0
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        if s[i] == '#':
            tokens.append({"tok": s[i:], "type": "comment"})
            break
        # f-string or string
        if s[i] in ('"', "'") or (s[i] == 'f' and i + 1 < len(s) and s[i+1] in ('"', "'")):
            start = i
            if s[i] == 'f':
                i += 1
            q = s[i]; i += 1
            while i < len(s) and s[i] != q:
                if s[i] == '\\': i += 1
                i += 1
            tokens.append({"tok": s[start:i+1], "type": "lit"})
            i += 1; continue
        # number
        if s[i].isdigit():
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] == '.'):
                j += 1
            tokens.append({"tok": s[i:j], "type": "lit"})
            i = j; continue
        # two-char op
        two = s[i:i+2]
        if two in OPS_TWO:
            tokens.append({"tok": two, "type": "op"})
            i += 2; continue
        # single-char op / punctuation
        if s[i] in '+-*/%=<>&|~^()[]{},:;.':
            tokens.append({"tok": s[i], "type": "op"})
            i += 1; continue
        # word
        if s[i].isalpha() or s[i] == '_':
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] == '_'):
                j += 1
            word = s[i:j]
            if word in KW_SET:
                py = KW_MAP[word]
                tokens.append({"tok": word, "type": "kw", "py": py if py else "(removed)"})
            else:
                tokens.append({"tok": word, "type": "ident"})
            i = j; continue
        tokens.append({"tok": s[i], "type": "op"})
        i += 1
    return {"indent": indent, "tokens": tokens}


def tokenize(code):
    result = []
    for idx, line in enumerate(code.split('\n')):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        row = _tokenize_line(line)
        row["line_num"] = idx + 1
        result.append(row)
    return result