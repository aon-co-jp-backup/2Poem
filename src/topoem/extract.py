"""Flask / FastAPI / Django のルートを Python のソースから取り出す(実行はしない。ast だけ)。"""
import ast
import os
import re
from dataclasses import dataclass, field

from .detect import detect_framework, parse_source

HTTP = ("get", "post", "put", "delete", "patch", "head", "options")
RUST_TYPES = {"int": "i64", "float": "f64", "str": "String", "string": "String", "path": "String", "uuid": "String", "slug": "String", "bool": "bool"}


@dataclass
class Param:
    name: str
    rust: str = "String"
    wildcard: bool = False


@dataclass
class Route:
    framework: str
    methods: list
    path: str  # 正規化済み: /items/:id (ワイルドカードは /files/*rest)
    handler: str
    params: list = field(default_factory=list)
    source: str = ""  # 元の関数のソース(先頭数行、コメントに使う)
    file: str = ""
    line: int = 0
    returns: str = "json"  # json | html | text | unknown
    notes: list = field(default_factory=list)


def _const_str(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


def _flask_path(raw):
    """/items/<int:id>/<name> → (/items/:id/:name, [Param...])"""
    params = []

    def rep(m):
        conv, name = (m.group(1) or "string"), m.group(2)
        conv = conv.rstrip(":")
        wild = conv == "path"
        params.append(Param(name, RUST_TYPES.get(conv, "String"), wild))
        return ("*" if wild else ":") + name

    return re.sub(r"<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>", rep, raw), params


def _fastapi_path(raw, func):
    ann = {}
    for a in func.args.args + func.args.kwonlyargs:
        if a.annotation is not None and isinstance(a.annotation, ast.Name):
            ann[a.arg] = a.annotation.id
    params = []

    def rep(m):
        name = m.group(1).split(":")[0]
        wild = m.group(1).endswith(":path")
        params.append(Param(name, RUST_TYPES.get(ann.get(name, "str"), "String"), wild))
        return ("*" if wild else ":") + name

    return re.sub(r"\{([^}]+)\}", rep, raw), params


def _django_path(raw):
    """<int:id>/ や (?P<id>\\d+) を /:id にする。先頭の ^ と末尾の $ は落とす。"""
    params = []

    def rep_conv(m):
        conv, name = (m.group(1) or "str"), m.group(2)
        wild = conv == "path"
        params.append(Param(name, RUST_TYPES.get(conv, "String"), wild))
        return ("*" if wild else ":") + name

    p = raw

    def rep_re(m):
        name = m.group(1)
        t = "i64" if r"\d" in m.group(2) else "String"
        params.append(Param(name, t))
        return ":" + name

    p = re.sub(r"\(\?P<(\w+)>([^)]*)\)", rep_re, p)
    p = re.sub(r"<(?:(\w+):)?(\w+)>", rep_conv, p)
    p = p.lstrip("^").rstrip("$")
    path = "/" + p.strip("/")
    params.sort(key=lambda q: path.find(":" + q.name) if path.find(":" + q.name) >= 0 else path.find("*" + q.name))
    return path, params


def _returns_kind(func):
    kinds = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Return) and n.value is not None:
            v = n.value
            if isinstance(v, ast.Dict):
                kinds.add("json")
            elif isinstance(v, ast.Call):
                nm = ast.unparse(v.func)
                if nm.endswith(("jsonify", "JSONResponse", "JsonResponse")):
                    kinds.add("json")
                elif nm.endswith(("render_template", "render", "TemplateResponse", "HTMLResponse")):
                    kinds.add("html")
                elif nm.endswith(("HttpResponse", "PlainTextResponse", "Response")):
                    kinds.add("text")
            elif isinstance(v, ast.Constant) and isinstance(v.value, str):
                kinds.add("text")
            elif isinstance(v, (ast.List, ast.Name, ast.Attribute, ast.Subscript)):
                kinds.add("json")
    return kinds.pop() if len(kinds) == 1 else ("json" if "json" in kinds else "unknown")


def _snippet(src_lines, func, limit=8):
    seg = src_lines[func.lineno - 1 : min(func.end_lineno, func.lineno - 1 + limit)]
    return "\n".join(seg)


def _decorator_routes(tree, src, file):
    lines = src.splitlines()
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.args):
                continue
            attr, raw = d.func.attr, _const_str(d.args[0])
            if raw is None:
                continue
            if attr == "route":
                methods = ["get"]
                for kw in d.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        methods = [_const_str(e).lower() for e in kw.value.elts if _const_str(e)] or methods
                fw = "flask"
            elif attr in HTTP:
                methods, fw = [attr], None
            else:
                continue
            is_fastapi = fw is None and ("{" in raw or any(k.arg in ("response_model", "status_code") for k in d.keywords))
            if fw == "flask" or (fw is None and "<" in raw and not is_fastapi):
                path, params = _flask_path(raw)
                fw = "flask"
            else:
                path, params = _fastapi_path(raw, node)
                fw = "fastapi" if fw is None else fw
            if not path.startswith("/"):
                path = "/" + path
            out.append(Route(fw, methods, path, node.name, params, _snippet(lines, node), file, node.lineno, _returns_kind(node)))
    return out


def _django_routes(tree, src, file, views):
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("path", "re_path", "url") and len(node.args) >= 2):
            continue
        raw = _const_str(node.args[0])
        if raw is None:
            continue
        target = node.args[1]
        if isinstance(target, ast.Call) and isinstance(target.func, ast.Attribute) and target.func.attr == "as_view":
            name = ast.unparse(target.func.value).split(".")[-1]
            methods = views.get(name, {}).get("methods", ["get", "post"])
            snippet, kind = views.get(name, {}).get("source", ""), "json"
        elif isinstance(target, (ast.Name, ast.Attribute)):
            name = ast.unparse(target).split(".")[-1]
            methods, snippet, kind = ["get", "post"], views.get(name, {}).get("source", ""), views.get(name, {}).get("returns", "json")
        else:
            continue  # include(...) などは追わない
        path, params = _django_path(raw)
        r = Route("django", methods, path, name, params, snippet, file, node.lineno, kind)
        if isinstance(target, ast.Call) or node.func.id == "re_path":
            r.notes.append("Django の正規表現/クラスベースビューは、メソッドとパスを推定しました")
        out.append(r)
    return out


def _collect_views(tree, src):
    lines = src.splitlines()
    views = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            views[node.name] = {"source": _snippet(lines, node), "returns": _returns_kind(node)}
        elif isinstance(node, ast.ClassDef):
            ms = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in HTTP]
            views[node.name] = {"methods": ms or ["get"], "source": _snippet(lines, node), "returns": "json"}
    return views


def extract_file(path):
    """1ファイルから (ルート一覧, 警告, 判定したフレームワーク, py2だったか)。"""
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    tree, warnings, py2 = parse_source(src)
    fws = detect_framework(tree)
    routes = _decorator_routes(tree, src, path)
    return routes, warnings, fws, py2, tree, src


def extract_project(root):
    """ファイルまたはディレクトリから全ルートを集める。(ルート, 警告, フレームワーク一覧, py2 のファイル一覧)"""
    files = []
    if os.path.isfile(root):
        files = [root]
    else:
        for d, dirs, fs in os.walk(root):
            dirs[:] = [x for x in dirs if x not in ("venv", ".venv", "node_modules", "__pycache__", ".git", "site-packages", "migrations")]
            files += [os.path.join(d, f) for f in fs if f.endswith(".py")]
    routes, warnings, fws, py2_files = [], [], [], []
    parsed = {}
    for f in sorted(files):
        try:
            r, w, fw, py2, tree, src = extract_file(f)
        except (SyntaxError, ValueError) as e:
            warnings.append("%s: 読めません(%s)" % (f, e))
            continue
        parsed[f] = (tree, src)
        routes += r
        warnings += ["%s: %s" % (f, x) for x in w]
        fws += [x for x in fw if x not in fws]
        if py2:
            py2_files.append(f)
    # Django: urls.py と views.py(同じフォルダ)
    for f, (tree, src) in parsed.items():
        if os.path.basename(f) == "urls.py":
            vf = os.path.join(os.path.dirname(f), "views.py")
            views = _collect_views(*parsed[vf]) if vf in parsed else {}
            routes += _django_routes(tree, src, f, views)
            if "django" not in fws:
                fws.append("django")
    return routes, warnings, fws, py2_files
