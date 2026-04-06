"""
Hinglish Compiler — translator.py
Pipeline: source → Lexer → [Token] → RDP Parser → AST → CodeGenerator → Python str
"""

import re

# ─────────────────────────────────────────────
#  Keyword map  (Hinglish → Python)
# ─────────────────────────────────────────────
KEYWORDS = {
    "warna_agar": "elif",
    "agar":       "if",
    "warna":      "else",
    "jabtak":     "while",
    "ke_liye":    "for",
    "mein":       "in",
    "band_karo":  "break",
    "agla":       "continue",
    "pass_karo":  "pass",
    "kaam":       "def",
    "wapas":      "return",
    "khud":       "self",
    "dikhao":     "print",
    "lo":         "input",
    "banao":      None,        # variable declaration — stripped
    "sach":       "True",
    "jhooth":     "False",
    "kuch_nahi":  "None",
    "aur":        "and",
    "ya":         "or",
    "nahi":       "not",
    "koshish":    "try",
    "pakdo":      "except",
    "antim":      "finally",
    "uthao":      "raise",
    "laao":       "import",
    "se":         "from",
    "lambai":     "len",
    "prakar":     "type",
    "seema":      "range",
    "andaza":     "int",
    "dasha_mlav": "float",
    "akshar":     "str",
    "suchi":      "list",
    "theli":      "dict",
    "samooh":     "set",
    "class":      "class",
}

# Python keywords that may appear verbatim in Hinglish code
PYTHON_KW = {
    "if", "elif", "else", "while", "for", "in", "break", "continue", "pass",
    "def", "return", "class", "self", "print", "input",
    "True", "False", "None", "and", "or", "not",
    "try", "except", "finally", "raise", "import", "from", "as",
    "len", "type", "range", "int", "float", "str", "list", "dict", "set",
    "lambda", "yield", "with", "global", "nonlocal", "del", "assert",
    "is", "not", "in",
}


# ─────────────────────────────────────────────
#  Token types
# ─────────────────────────────────────────────
TT_KW      = "KW"        # Hinglish keyword (translated)
TT_NAME    = "NAME"      # identifier
TT_NUMBER  = "NUMBER"
TT_STRING  = "STRING"
TT_OP      = "OP"
TT_NEWLINE = "NEWLINE"
TT_INDENT  = "INDENT"
TT_DEDENT  = "DEDENT"
TT_EOF     = "EOF"
TT_COMMENT = "COMMENT"


class Token:
    def __init__(self, type_, value, line=0, hinglish=None):
        self.type     = type_
        self.value    = value      # Python value after translation
        self.line     = line
        self.hinglish = hinglish   # original Hinglish word if translated

    def __repr__(self):
        h = f"←{self.hinglish}" if self.hinglish else ""
        return f"Token({self.type}, {self.value!r}{h}, L{self.line})"

    def to_dict(self):
        return {
            "type":     self.type,
            "value":    self.value,
            "line":     self.line,
            "hinglish": self.hinglish,
        }


# ─────────────────────────────────────────────
#  Lexer
# ─────────────────────────────────────────────
TWO_CHAR_OPS = {"==", "!=", "<=", ">=", "**", "//", "+=", "-=", "*=", "/=",
                "->", "<<", ">>"}

class Lexer:
    def __init__(self, source):
        self.source = source
        self.lines  = source.splitlines(keepends=True)
        self.tokens = []
        self._tokenize()

    def _tokenize(self):
        indent_stack = [0]
        for lineno, raw_line in enumerate(self.lines, start=1):
            line = raw_line.rstrip("\n\r")
            stripped = line.lstrip()

            if not stripped or stripped.startswith("#"):
                continue  # skip blank / comment lines for indent tracking

            # ── Indentation ──
            indent = len(line) - len(stripped)
            if indent > indent_stack[-1]:
                indent_stack.append(indent)
                self.tokens.append(Token(TT_INDENT, indent, lineno))
            while indent < indent_stack[-1]:
                indent_stack.pop()
                self.tokens.append(Token(TT_DEDENT, indent_stack[-1], lineno))

            # ── Lex tokens on this line ──
            self._lex_line(stripped, lineno)
            self.tokens.append(Token(TT_NEWLINE, "\n", lineno))

        # close remaining indents
        while len(indent_stack) > 1:
            indent_stack.pop()
            self.tokens.append(Token(TT_DEDENT, 0, len(self.lines)))

        self.tokens.append(Token(TT_EOF, "", len(self.lines)))

    def _lex_line(self, s, lineno):
        i = 0
        while i < len(s):
            c = s[i]

            if c.isspace():
                i += 1
                continue

            # comment
            if c == "#":
                self.tokens.append(Token(TT_COMMENT, s[i:], lineno))
                return

            # f-string or string
            if c in ('"', "'") or (c == 'f' and i+1 < len(s) and s[i+1] in ('"', "'")):
                tok, length = self._read_string(s, i)
                self.tokens.append(Token(TT_STRING, tok, lineno))
                i += length
                continue

            # number
            if c.isdigit() or (c == '.' and i+1 < len(s) and s[i+1].isdigit()):
                j = i
                while j < len(s) and (s[j].isdigit() or s[j] == '.'):
                    j += 1
                self.tokens.append(Token(TT_NUMBER, s[i:j], lineno))
                i = j
                continue

            # two-char operator
            two = s[i:i+2]
            if two in TWO_CHAR_OPS:
                self.tokens.append(Token(TT_OP, two, lineno))
                i += 2
                continue

            # single-char operator / punctuation
            if c in r'+-*/%=<>&|~^()[]{},:;.@':
                self.tokens.append(Token(TT_OP, c, lineno))
                i += 1
                continue

            # word — keyword or name
            if c.isalpha() or c == '_':
                j = i
                while j < len(s) and (s[j].isalnum() or s[j] == '_'):
                    j += 1
                word = s[i:j]
                if word in KEYWORDS:
                    py = KEYWORDS[word]
                    if py is None:          # banao → stripped
                        i = j
                        continue
                    self.tokens.append(Token(TT_KW, py, lineno, hinglish=word))
                elif word in PYTHON_KW:
                    self.tokens.append(Token(TT_KW, word, lineno))
                else:
                    self.tokens.append(Token(TT_NAME, word, lineno))
                i = j
                continue

            # unknown — pass through
            self.tokens.append(Token(TT_OP, c, lineno))
            i += 1

    def _read_string(self, s, start):
        i = start
        prefix = ""
        if s[i] == 'f':
            prefix = 'f'
            i += 1
        q = s[i]
        # triple-quote?
        if s[i:i+3] in ('"""', "'''"):
            q = s[i:i+3]
            i += 3
        else:
            i += 1
        while i < len(s):
            if s[i] == '\\':
                i += 2
                continue
            if s[i:i+len(q)] == q:
                i += len(q)
                break
            i += 1
        tok = s[start:i]
        return tok, i - start


# ─────────────────────────────────────────────
#  AST nodes
# ─────────────────────────────────────────────
class ASTNode:
    """Generic AST node. children is a list of ASTNode or Token."""
    def __init__(self, kind, value=None, children=None, line=0):
        self.kind     = kind       # e.g. "Program", "IfStmt", "BinOp"
        self.value    = value      # literal value if leaf
        self.children = children or []
        self.line     = line

    def to_dict(self):
        return {
            "kind":     self.kind,
            "value":    self.value,
            "line":     self.line,
            "children": [
                c.to_dict() if isinstance(c, ASTNode)
                else (c.to_dict() if isinstance(c, Token) else {"kind": "raw", "value": str(c)})
                for c in self.children
            ],
        }


# ─────────────────────────────────────────────
#  Recursive Descent Parser
# ─────────────────────────────────────────────
class ParseError(Exception):
    def __init__(self, msg, line=0):
        super().__init__(f"Line {line}: {msg}")
        self.line = line


class Parser:
    """
    Grammar (simplified):
      program     → stmt* EOF
      stmt        → if_stmt | while_stmt | for_stmt | def_stmt
                  | class_stmt | try_stmt | return_stmt | import_stmt
                  | expr_stmt | NEWLINE
      if_stmt     → 'if' expr ':' block ('elif' expr ':' block)* ('else' ':' block)?
      while_stmt  → 'while' expr ':' block
      for_stmt    → 'for' NAME 'in' expr ':' block
      def_stmt    → 'def' NAME '(' params ')' ':' block
      class_stmt  → 'class' NAME ('(' NAME ')')? ':' block
      try_stmt    → 'try' ':' block ('except' expr? ':' block)* ('finally' ':' block)?
      return_stmt → 'return' expr?
      import_stmt → 'import' NAME | 'from' NAME 'import' NAME
      expr_stmt   → expr ('=' expr)?
      block       → NEWLINE INDENT stmt+ DEDENT
      expr        → or_expr
      or_expr     → and_expr ('or' and_expr)*
      and_expr    → not_expr ('and' not_expr)*
      not_expr    → 'not' not_expr | compare
      compare     → arith (CMP_OP arith)*
      arith       → term (('+' | '-') term)*
      term        → factor (('*' | '/' | '//' | '%' | '**') factor)*
      factor      → ('+' | '-') factor | power
      power       → atom trailer*
      trailer     → '(' arglist ')' | '[' expr ']' | '.' NAME
      atom        → NUMBER | STRING | NAME | '(' expr ')' | '[' exprlist ']'
                  | '{' dictorset '}'
    """

    def __init__(self, tokens):
        self.tokens = [t for t in tokens if t.type != TT_COMMENT]
        self.pos    = 0

    # ── helpers ──────────────────────────────

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return Token(TT_EOF, "")

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def eat(self, type_=None, value=None):
        tok = self.peek()
        if type_ and tok.type != type_:
            raise ParseError(f"Expected token type {type_!r}, got {tok.type!r} ({tok.value!r})", tok.line)
        if value and tok.value != value:
            raise ParseError(f"Expected {value!r}, got {tok.value!r}", tok.line)
        return self.advance()

    def match(self, type_=None, value=None, offset=0):
        tok = self.peek(offset)
        if type_ and tok.type != type_:
            return False
        if value and tok.value != value:
            return False
        return True

    def skip_newlines(self):
        while self.match(TT_NEWLINE):
            self.advance()

    # ── entry ─────────────────────────────────

    def parse(self):
        self.skip_newlines()
        stmts = []
        while not self.match(TT_EOF):
            s = self.parse_stmt()
            if s:
                stmts.append(s)
            self.skip_newlines()
        return ASTNode("Program", children=stmts)

    # ── statements ────────────────────────────

    def parse_stmt(self):
        tok = self.peek()

        if tok.type == TT_NEWLINE:
            self.advance()
            return None

        if tok.type in (TT_INDENT, TT_DEDENT):
            self.advance()
            return None

        if tok.type == TT_KW:
            v = tok.value
            if v == "if":      return self.parse_if()
            if v == "while":   return self.parse_while()
            if v == "for":     return self.parse_for()
            if v == "def":     return self.parse_def()
            if v == "class":   return self.parse_class()
            if v == "try":     return self.parse_try()
            if v == "return":  return self.parse_return()
            if v == "import":  return self.parse_import()
            if v == "from":    return self.parse_from()
            if v == "break":
                self.advance()
                return ASTNode("Break", line=tok.line)
            if v == "continue":
                self.advance()
                return ASTNode("Continue", line=tok.line)
            if v == "pass":
                self.advance()
                return ASTNode("Pass", line=tok.line)
            if v == "raise":
                self.advance()
                expr = None
                if not self.match(TT_NEWLINE) and not self.match(TT_EOF):
                    expr = self.parse_expr()
                return ASTNode("Raise", children=[expr] if expr else [], line=tok.line)

        return self.parse_expr_stmt()

    def parse_if(self):
        line = self.peek().line
        self.eat(TT_KW, "if")
        cond = self.parse_expr()
        self.eat(TT_OP, ":")
        body = self.parse_block()
        node = ASTNode("IfStmt", children=[cond, ASTNode("Body", children=body)], line=line)
        while self.match(TT_KW, "elif"):
            self.advance()
            ec = self.parse_expr()
            self.eat(TT_OP, ":")
            eb = self.parse_block()
            node.children.append(ASTNode("ElifClause", children=[ec, ASTNode("Body", children=eb)]))
        if self.match(TT_KW, "else"):
            self.advance()
            self.eat(TT_OP, ":")
            eb = self.parse_block()
            node.children.append(ASTNode("ElseClause", children=eb))
        return node

    def parse_while(self):
        line = self.peek().line
        self.eat(TT_KW, "while")
        cond = self.parse_expr()
        self.eat(TT_OP, ":")
        body = self.parse_block()
        return ASTNode("WhileStmt", children=[cond, ASTNode("Body", children=body)], line=line)

    def parse_for(self):
        line = self.peek().line
        self.eat(TT_KW, "for")
        var = self.eat(TT_NAME)
        self.eat(TT_KW, "in")
        iterable = self.parse_expr()
        self.eat(TT_OP, ":")
        body = self.parse_block()
        return ASTNode("ForStmt", value=var.value,
                       children=[iterable, ASTNode("Body", children=body)], line=line)

    def parse_def(self):
        line = self.peek().line
        self.eat(TT_KW, "def")
        name = self.eat(TT_NAME)
        self.eat(TT_OP, "(")
        params = self.parse_params()
        self.eat(TT_OP, ")")
        self.eat(TT_OP, ":")
        body = self.parse_block()
        return ASTNode("FuncDef", value=name.value,
                       children=[ASTNode("Params", children=[ASTNode("Param", value=p) for p in params]),
                                 ASTNode("Body", children=body)], line=line)

    def parse_class(self):
        line = self.peek().line
        self.eat(TT_KW, "class")
        name = self.eat(TT_NAME)
        bases = []
        if self.match(TT_OP, "("):
            self.advance()
            while not self.match(TT_OP, ")"):
                bases.append(self.eat(TT_NAME).value)
                if self.match(TT_OP, ","):
                    self.advance()
            self.eat(TT_OP, ")")
        self.eat(TT_OP, ":")
        body = self.parse_block()
        return ASTNode("ClassDef", value=name.value,
                       children=[ASTNode("Bases", children=[ASTNode("Base", value=b) for b in bases]),
                                 ASTNode("Body", children=body)], line=line)

    def parse_try(self):
        line = self.peek().line
        self.eat(TT_KW, "try")
        self.eat(TT_OP, ":")
        body = self.parse_block()
        node = ASTNode("TryStmt", children=[ASTNode("Body", children=body)], line=line)
        while self.match(TT_KW, "except"):
            self.advance()
            exc = None
            if not self.match(TT_OP, ":"):
                exc = self.parse_expr()
            self.eat(TT_OP, ":")
            eb = self.parse_block()
            clause = ASTNode("ExceptClause", children=[ASTNode("Body", children=eb)])
            if exc:
                clause.children.insert(0, exc)
            node.children.append(clause)
        if self.match(TT_KW, "finally"):
            self.advance()
            self.eat(TT_OP, ":")
            fb = self.parse_block()
            node.children.append(ASTNode("FinallyClause", children=fb))
        return node

    def parse_return(self):
        line = self.peek().line
        self.eat(TT_KW, "return")
        if self.match(TT_NEWLINE) or self.match(TT_EOF) or self.match(TT_DEDENT):
            return ASTNode("Return", line=line)
        expr = self.parse_expr()
        return ASTNode("Return", children=[expr], line=line)

    def parse_import(self):
        line = self.peek().line
        self.eat(TT_KW, "import")
        name = self.eat(TT_NAME)
        return ASTNode("Import", value=name.value, line=line)

    def parse_from(self):
        line = self.peek().line
        self.eat(TT_KW, "from")
        mod = self.eat(TT_NAME)
        self.eat(TT_KW, "import")
        name = self.eat(TT_NAME)
        return ASTNode("FromImport", value=f"{mod.value}.{name.value}", line=line)

    def parse_expr_stmt(self):
        line = self.peek().line
        expr = self.parse_expr()
        # augmented or plain assignment
        if self.match(TT_OP) and self.peek().value in ("=", "+=", "-=", "*=", "/="):
            op = self.advance().value
            rhs = self.parse_expr()
            return ASTNode("Assign", value=op, children=[expr, rhs], line=line)
        return ASTNode("ExprStmt", children=[expr], line=line)

    def parse_block(self):
        self.eat(TT_NEWLINE)
        self.skip_newlines()
        self.eat(TT_INDENT)
        stmts = []
        while not self.match(TT_DEDENT) and not self.match(TT_EOF):
            s = self.parse_stmt()
            if s:
                stmts.append(s)
        if self.match(TT_DEDENT):
            self.advance()
        return stmts

    def parse_params(self):
        params = []
        while not self.match(TT_OP, ")"):
            if self.match(TT_NAME) or self.match(TT_KW, "self"):
                params.append(self.advance().value)
            if self.match(TT_OP, ","):
                self.advance()
            else:
                break
        return params

    # ── expressions ───────────────────────────

    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.match(TT_KW, "or"):
            op = self.advance()
            right = self.parse_and()
            left = ASTNode("BinOp", value="or", children=[left, right], line=op.line)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.match(TT_KW, "and"):
            op = self.advance()
            right = self.parse_not()
            left = ASTNode("BinOp", value="and", children=[left, right], line=op.line)
        return left

    def parse_not(self):
        if self.match(TT_KW, "not"):
            op = self.advance()
            operand = self.parse_not()
            return ASTNode("UnaryOp", value="not", children=[operand], line=op.line)
        return self.parse_compare()

    CMP_OPS = {"==", "!=", "<", ">", "<=", ">=", "is", "in"}

    def parse_compare(self):
        left = self.parse_arith()
        while True:
            tok = self.peek()
            if tok.type == TT_OP and tok.value in self.CMP_OPS:
                op = self.advance()
                right = self.parse_arith()
                left = ASTNode("BinOp", value=op.value, children=[left, right], line=op.line)
            elif tok.type == TT_KW and tok.value in ("in", "is"):
                op = self.advance()
                right = self.parse_arith()
                left = ASTNode("BinOp", value=op.value, children=[left, right], line=op.line)
            elif tok.type == TT_KW and tok.value == "not" and self.peek(1).value == "in":
                self.advance(); self.advance()
                right = self.parse_arith()
                left = ASTNode("BinOp", value="not in", children=[left, right], line=tok.line)
            else:
                break
        return left

    def parse_arith(self):
        left = self.parse_term()
        while self.match(TT_OP) and self.peek().value in ("+", "-"):
            op = self.advance()
            right = self.parse_term()
            left = ASTNode("BinOp", value=op.value, children=[left, right], line=op.line)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.match(TT_OP) and self.peek().value in ("*", "/", "//", "%", "**"):
            op = self.advance()
            right = self.parse_factor()
            left = ASTNode("BinOp", value=op.value, children=[left, right], line=op.line)
        return left

    def parse_factor(self):
        if self.match(TT_OP) and self.peek().value in ("+", "-", "~"):
            op = self.advance()
            operand = self.parse_factor()
            return ASTNode("UnaryOp", value=op.value, children=[operand], line=op.line)
        return self.parse_power()

    def parse_power(self):
        base = self.parse_atom()
        # trailers: calls, subscripts, attributes
        while True:
            if self.match(TT_OP, "("):
                line = self.peek().line
                self.advance()
                args = self.parse_arglist()
                self.eat(TT_OP, ")")
                base = ASTNode("Call", children=[base] + args, line=line)
            elif self.match(TT_OP, "["):
                line = self.peek().line
                self.advance()
                idx = self.parse_expr()
                self.eat(TT_OP, "]")
                base = ASTNode("Subscript", children=[base, idx], line=line)
            elif self.match(TT_OP, "."):
                line = self.peek().line
                self.advance()
                attr = self.eat(TT_NAME)
                base = ASTNode("Attr", value=attr.value, children=[base], line=line)
            else:
                break
        return base

    def parse_atom(self):
        tok = self.peek()

        if tok.type == TT_NUMBER:
            self.advance()
            return ASTNode("Number", value=tok.value, line=tok.line)

        if tok.type == TT_STRING:
            self.advance()
            return ASTNode("String", value=tok.value, line=tok.line)

        if tok.type == TT_NAME:
            self.advance()
            return ASTNode("Name", value=tok.value, line=tok.line)

        if tok.type == TT_KW and tok.value in ("True", "False", "None",
                                                "print", "input", "len", "type",
                                                "range", "int", "float", "str",
                                                "list", "dict", "set", "self"):
            self.advance()
            return ASTNode("Name", value=tok.value, line=tok.line,
                           children=[ASTNode("_hinglish", value=tok.hinglish)] if tok.hinglish else [])

        if tok.type == TT_OP and tok.value == "(":
            self.advance()
            if self.match(TT_OP, ")"):
                self.advance()
                return ASTNode("Tuple", children=[], line=tok.line)
            expr = self.parse_expr()
            # tuple?
            if self.match(TT_OP, ","):
                items = [expr]
                while self.match(TT_OP, ","):
                    self.advance()
                    if self.match(TT_OP, ")"):
                        break
                    items.append(self.parse_expr())
                self.eat(TT_OP, ")")
                return ASTNode("Tuple", children=items, line=tok.line)
            self.eat(TT_OP, ")")
            return expr

        if tok.type == TT_OP and tok.value == "[":
            line = tok.line
            self.advance()
            items = []
            while not self.match(TT_OP, "]") and not self.match(TT_EOF):
                items.append(self.parse_expr())
                if self.match(TT_OP, ","):
                    self.advance()
            self.eat(TT_OP, "]")
            return ASTNode("List", children=items, line=line)

        if tok.type == TT_OP and tok.value == "{":
            line = tok.line
            self.advance()
            items = []
            while not self.match(TT_OP, "}") and not self.match(TT_EOF):
                k = self.parse_expr()
                if self.match(TT_OP, ":"):
                    self.advance()
                    v = self.parse_expr()
                    items.append(ASTNode("KVPair", children=[k, v]))
                else:
                    items.append(k)
                if self.match(TT_OP, ","):
                    self.advance()
            self.eat(TT_OP, "}")
            return ASTNode("DictOrSet", children=items, line=line)

        if tok.type in (TT_NEWLINE, TT_EOF, TT_DEDENT):
            return ASTNode("Empty", line=tok.line)

        # fallback — consume and wrap
        self.advance()
        return ASTNode("Unknown", value=tok.value, line=tok.line)

    def parse_arglist(self):
        args = []
        while not self.match(TT_OP, ")") and not self.match(TT_EOF):
            args.append(self.parse_expr())
            if self.match(TT_OP, ","):
                self.advance()
            else:
                break
        return args


# ─────────────────────────────────────────────
#  Code Generator  (AST → Python source)
# ─────────────────────────────────────────────
class CodeGenerator:
    def __init__(self):
        self._indent = 0

    def indent(self):
        return "    " * self._indent

    def generate(self, node):
        if node is None:
            return ""
        method = getattr(self, "gen_" + node.kind, self.gen_unknown)
        return method(node)

    def gen_Program(self, n):
        return "\n".join(self.generate(c) for c in n.children if c)

    def gen_ExprStmt(self, n):
        return self.indent() + self.generate(n.children[0])

    def gen_Assign(self, n):
        lhs = self.generate(n.children[0])
        rhs = self.generate(n.children[1])
        return self.indent() + f"{lhs} {n.value} {rhs}"

    def gen_IfStmt(self, n):
        cond  = self.generate(n.children[0])
        body  = self._gen_body(n.children[1])
        lines = [self.indent() + f"if {cond}:\n{body}"]
        for clause in n.children[2:]:
            if clause.kind == "ElifClause":
                ec   = self.generate(clause.children[0])
                eb   = self._gen_body(clause.children[1])
                lines.append(self.indent() + f"elif {ec}:\n{eb}")
            elif clause.kind == "ElseClause":
                self._indent += 1
                eb = "\n".join(self.generate(s) for s in clause.children if s)
                self._indent -= 1
                lines.append(self.indent() + f"else:\n{eb}")
        return "\n".join(lines)

    def gen_WhileStmt(self, n):
        cond = self.generate(n.children[0])
        body = self._gen_body(n.children[1])
        return self.indent() + f"while {cond}:\n{body}"

    def gen_ForStmt(self, n):
        var  = n.value
        it   = self.generate(n.children[0])
        body = self._gen_body(n.children[1])
        return self.indent() + f"for {var} in {it}:\n{body}"

    def gen_FuncDef(self, n):
        name   = n.value
        params = ", ".join(c.value for c in n.children[0].children)
        body   = self._gen_body(n.children[1])
        return self.indent() + f"def {name}({params}):\n{body}"

    def gen_ClassDef(self, n):
        name  = n.value
        bases = n.children[0].children
        base_str = "(" + ", ".join(b.value for b in bases) + ")" if bases else ""
        body  = self._gen_body(n.children[1])
        return self.indent() + f"class {name}{base_str}:\n{body}"

    def gen_TryStmt(self, n):
        body  = self._gen_body(n.children[0])
        lines = [self.indent() + f"try:\n{body}"]
        for clause in n.children[1:]:
            if clause.kind == "ExceptClause":
                self._indent += 1
                cb = "\n".join(self.generate(s) for s in clause.children if s and s.kind == "Body"
                               for s in (s.children if s.kind == "Body" else [s]) if s)
                self._indent -= 1
                # find exception type if present
                exc_nodes = [c for c in clause.children if c.kind != "Body"]
                exc_str   = self.generate(exc_nodes[0]) if exc_nodes else ""
                cb2 = self._gen_body_list([c for c in clause.children if c.kind == "Body"])
                lines.append(self.indent() + f"except {exc_str}:\n{cb2}".rstrip(": ") + ":")
                # redo cleanly
                exc_type = ""
                body_node = None
                for ch in clause.children:
                    if ch.kind == "Body":
                        body_node = ch
                    else:
                        exc_type = self.generate(ch)
                exc_line = f"except {exc_type}:" if exc_type else "except:"
                b = self._gen_body(body_node) if body_node else self.indent() + "    pass"
                lines[-1] = self.indent() + exc_line + "\n" + b
            elif clause.kind == "FinallyClause":
                self._indent += 1
                fb = "\n".join(self.generate(s) for s in clause.children if s)
                self._indent -= 1
                lines.append(self.indent() + f"finally:\n{fb}")
        return "\n".join(lines)

    def gen_Return(self, n):
        if n.children:
            return self.indent() + "return " + self.generate(n.children[0])
        return self.indent() + "return"

    def gen_Import(self, n):
        return self.indent() + f"import {n.value}"

    def gen_FromImport(self, n):
        parts = n.value.split(".")
        return self.indent() + f"from {parts[0]} import {parts[1]}"

    def gen_Break(self, n):    return self.indent() + "break"
    def gen_Continue(self, n): return self.indent() + "continue"
    def gen_Pass(self, n):     return self.indent() + "pass"

    def gen_Raise(self, n):
        if n.children:
            return self.indent() + "raise " + self.generate(n.children[0])
        return self.indent() + "raise"

    def gen_BinOp(self, n):
        l = self._maybe_paren(n.children[0], n.value)
        r = self._maybe_paren(n.children[1], n.value)
        return f"{l} {n.value} {r}"

    def gen_UnaryOp(self, n):
        op  = n.value
        sep = " " if op == "not" else ""
        return f"{op}{sep}{self.generate(n.children[0])}"

    def gen_Call(self, n):
        func = self.generate(n.children[0])
        args = ", ".join(self.generate(a) for a in n.children[1:])
        return f"{func}({args})"

    def gen_Subscript(self, n):
        return f"{self.generate(n.children[0])}[{self.generate(n.children[1])}]"

    def gen_Attr(self, n):
        return f"{self.generate(n.children[0])}.{n.value}"

    def gen_Name(self, n):    return str(n.value)
    def gen_Number(self, n):  return str(n.value)
    def gen_String(self, n):  return str(n.value)

    def gen_List(self, n):
        return "[" + ", ".join(self.generate(c) for c in n.children) + "]"

    def gen_Tuple(self, n):
        items = ", ".join(self.generate(c) for c in n.children)
        return f"({items},)" if len(n.children) == 1 else f"({items})"

    def gen_DictOrSet(self, n):
        parts = []
        for c in n.children:
            if c.kind == "KVPair":
                parts.append(self.generate(c.children[0]) + ": " + self.generate(c.children[1]))
            else:
                parts.append(self.generate(c))
        return "{" + ", ".join(parts) + "}"

    def gen_Empty(self, n):   return ""
    def gen_unknown(self, n): return str(n.value or "")

    # helpers
    def _gen_body(self, body_node):
        if body_node is None:
            return self.indent() + "    pass"
        self._indent += 1
        lines = [self.generate(s) for s in body_node.children if s]
        self._indent -= 1
        return "\n".join(l for l in lines if l)

    def _gen_body_list(self, body_nodes):
        for bn in body_nodes:
            return self._gen_body(bn)
        return ""

    def _maybe_paren(self, node, parent_op):
        s = self.generate(node)
        # wrap lower-precedence binary ops in parens
        if node.kind == "BinOp" and node.value in ("or", "and") and parent_op not in ("or",):
            return f"({s})"
        return s


# ─────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────
def translate(source: str) -> str:
    """Hinglish source → Python source string."""
    lexer  = Lexer(source)
    parser = Parser(lexer.tokens)
    ast    = parser.parse()
    gen    = CodeGenerator()
    return gen.generate(ast)


def parse_to_ast(source: str) -> dict:
    """Return the AST as a JSON-serialisable dict (for the parse-tree panel)."""
    try:
        lexer  = Lexer(source)
        parser = Parser(lexer.tokens)
        ast    = parser.parse()
        return {"ok": True,  "ast": ast.to_dict(), "error": None}
    except ParseError as e:
        return {"ok": False, "ast": None, "error": str(e)}
    except Exception as e:
        return {"ok": False, "ast": None, "error": f"Internal error: {e}"}