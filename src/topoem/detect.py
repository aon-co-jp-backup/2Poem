"""フレームワーク・Python の世代の判定と、Python 2 の最低限の3系化。

Python の新しい文法は、実行しているインタープリター自身の `ast` で読む(= 新しい Python を入れれば、その文法にそのまま追従する)。
Python 2 のソースは、よくある構文だけを機械的に3系へ直してから読む(完全ではない。直せなかった箇所は警告に出す)。
"""
import ast
import re

PY2_PATTERNS = [
    (re.compile(r"^\s*print\s+[^(=\s]", re.M), "print 文"),
    (re.compile(r"^\s*except\s+[\w.]+\s*,\s*\w+\s*:", re.M), "except X, e"),
    (re.compile(r"^\s*raise\s+\w+\s*,\s*", re.M), "raise X, msg"),
    (re.compile(r"\bur[\"']"), "ur リテラル"),
    (re.compile(r"<>"), "<> 演算子"),
    (re.compile(r"^\s*exec\s+[\"'\w]", re.M), "exec 文"),
    (re.compile(r"\bunicode\s*\("), "unicode()"),
    (re.compile(r"\.iteritems\s*\(|\.itervalues\s*\(|\.iterkeys\s*\(|\.has_key\s*\("), "辞書の旧メソッド"),
]


def looks_like_py2(src):
    """Python 2 らしい構文の名前を返す(無ければ空)。"""
    return [name for pat, name in PY2_PATTERNS if pat.search(src)]


def py2_to_py3(src):
    """よくある Python 2 構文を3系へ直す。(直したソース, 直した件数, 直せなかった可能性のある点)"""
    n = 0
    notes = []

    def sub(pat, rep, flags=re.M):
        nonlocal n
        s, c = re.subn(pat, rep, src_holder[0], flags=flags)
        src_holder[0] = s
        n += c

    src_holder = [src]
    sub(r"^(\s*)print\s+((?![(=\s]).+?)\s*$", r"\1print(\2)")
    sub(r"^(\s*)except\s+([\w.]+)\s*,\s*(\w+)\s*:", r"\1except \2 as \3:")
    sub(r"^(\s*)raise\s+(\w+)\s*,\s*(.+?)\s*$", r"\1raise \2(\3)")
    sub(r"\bur([\"'])", r"u\1", 0)
    sub(r"<>", "!=", 0)
    sub(r"\.iteritems\s*\(\s*\)", ".items()", 0)
    sub(r"\.itervalues\s*\(\s*\)", ".values()", 0)
    sub(r"\.iterkeys\s*\(\s*\)", ".keys()", 0)
    sub(r"\bunicode\s*\(", "str(", 0)
    out = src_holder[0]
    if re.search(r"^\s*exec\s+[\"'\w]", out, re.M):
        notes.append("exec 文は自動では直せません")
    if re.search(r"\.has_key\s*\(", out):
        notes.append("has_key() は `in` へ手で直してください")
    return out, n, notes


def parse_source(src):
    """ソースを ast にする。(木, 警告のリスト, py2 だったか)。読めなければ SyntaxError。"""
    warnings = []
    try:
        return ast.parse(src), warnings, False
    except SyntaxError as first:
        py2 = looks_like_py2(src)
        if not py2:
            raise first
        fixed, n, notes = py2_to_py3(src)
        warnings.append("Python 2 のソースを3系へ変換して読みました(%d 箇所: %s)" % (n, ", ".join(py2)))
        warnings.extend(notes)
        return ast.parse(fixed), warnings, True


def detect_framework(tree):
    """import から Flask / Django / FastAPI を判定する(複数あれば最初に見つかったもの)。"""
    found = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for nm in names:
            top = nm.split(".")[0].lower()
            if top in ("flask", "django", "fastapi") and top not in found:
                found.append(top)
    return found
