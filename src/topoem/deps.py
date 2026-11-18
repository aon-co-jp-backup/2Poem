"""既存システムの依存の検出と、新版への書き換え(JavaScript / TypeScript / React / WunderGraph Cosmo / DB / Python フレームワーク)。

検出: package.json、requirements*.txt、pyproject.toml、Cargo.toml、Django の `DATABASES`、docker-compose の DB イメージ。
書き換え(`--apply`): package.json と requirements*.txt の版指定を最新へ。元ファイルは `.2poem.bak` に残す。
メジャー更新は壊れやすいので既定では **マイナー/パッチのみ**(`--major` で解禁)。lock ファイルは触らない(更新後に自分で再生成する)。
"""
import json
import os
import re

from . import versions

# 種別 → 判定する名前(npm / PyPI / crates)
KINDS = [
    ("bootstrap", {"bootstrap", "react-bootstrap", "bootstrap-icons", "@popperjs/core", "reactstrap", "bootstrap-vue", "ngx-bootstrap", "django-bootstrap5", "django-bootstrap4", "flask-bootstrap", "bootstrap-flask"}),
    ("react", {"react", "react-dom", "next", "react-router", "react-router-dom"}),
    ("typescript", {"typescript", "ts-node", "tsx", "@types/node", "@types/react"}),
    ("cosmo", {"wgc", "@wundergraph/cosmo-connect", "@wundergraph/composition", "@wundergraph/protographic", "@wundergraph/sdk", "@wundergraph/nextjs"}),
    ("db", {"pg", "mysql", "mysql2", "sqlite3", "better-sqlite3", "mongodb", "mongoose", "prisma", "@prisma/client", "typeorm", "sequelize", "knex", "drizzle-orm", "redis", "ioredis",
            "psycopg2", "psycopg2-binary", "psycopg", "mysqlclient", "pymysql", "sqlalchemy", "flask-sqlalchemy", "pymongo", "asyncpg", "aiosqlite", "alembic", "sqlx", "diesel", "tokio-postgres", "rusqlite"}),
    ("python-fw", {"django", "flask", "fastapi", "starlette", "djangorestframework", "uvicorn", "gunicorn"}),
    ("rust", {"poem", "poem-openapi", "axum", "actix-web", "tokio"}),
]


def kind_of(name):
    n = name.lower()
    for k, names in KINDS:
        if n in names or (k == "cosmo" and n.startswith("@wundergraph/")):
            return k
    return None


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def scan(root):
    """依存の一覧: [{file, eco, name, spec, kind}]。eco は npm / pypi / crates。"""
    found = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("node_modules", "venv", ".venv", ".git", "target", "__pycache__", "dist", "build")]
        for fn in files:
            p = os.path.join(d, fn)
            if fn == "package.json":
                try:
                    j = json.loads(_read(p) or "{}")
                except ValueError:
                    continue
                for sec in ("dependencies", "devDependencies", "peerDependencies"):
                    for n, spec in (j.get(sec) or {}).items():
                        found.append({"file": p, "eco": "npm", "name": n, "spec": str(spec), "kind": kind_of(n) or "javascript"})
            elif re.fullmatch(r"requirements.*\.txt", fn):
                for line in (_read(p) or "").splitlines():
                    m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*((?:==|>=|~=|<=|>|<|!=)\s*[\w.*]+)?", line)
                    if m and not line.strip().startswith(("#", "-")):
                        found.append({"file": p, "eco": "pypi", "name": m.group(1), "spec": (m.group(2) or "").replace(" ", ""), "kind": kind_of(m.group(1)) or "python"})
            elif fn == "Cargo.toml":
                sec = None
                for line in (_read(p) or "").splitlines():
                    s = line.strip()
                    if s.startswith("["):
                        sec = s
                        continue
                    if sec and "dependencies" in sec:
                        m = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*(?:"([^"]+)"|\{[^}]*version\s*=\s*"([^"]+)")', s)
                        if m:
                            found.append({"file": p, "eco": "crates", "name": m.group(1), "spec": m.group(2) or m.group(3), "kind": kind_of(m.group(1)) or "rust"})
            elif fn.endswith((".html", ".htm", ".jinja", ".jinja2", ".j2", ".twig")):
                # テンプレートに直書きした CDN の Bootstrap(例: bootstrap@5.3.3 / bootstrap/5.3.3/css/...)
                for m in re.finditer(r"bootstrap(?:@|/)(\d+\.\d+(?:\.\d+)?)", _read(p) or ""):
                    found.append({"file": p, "eco": "cdn", "name": "bootstrap", "spec": m.group(1), "kind": "bootstrap"})
            elif fn == "settings.py":
                for m in re.finditer(r"django\.db\.backends\.(\w+)|django\.contrib\.gis\.db\.backends\.(\w+)", _read(p) or ""):
                    found.append({"file": p, "eco": "db-engine", "name": m.group(1) or m.group(2), "spec": "", "kind": "db"})
            elif fn.startswith("docker-compose") and fn.endswith((".yml", ".yaml")):
                for m in re.finditer(r"image:\s*['\"]?(postgres|mysql|mariadb|mongo|redis)(?::([\w.\-]+))?", _read(p) or ""):
                    found.append({"file": p, "eco": "docker", "name": m.group(1), "spec": m.group(2) or "latest", "kind": "db"})
    return found


def latest_of(dep, get=versions._get):
    try:
        if dep["eco"] == "npm":
            return versions.npm(dep["name"], get)
        if dep["eco"] == "pypi":
            return versions.pypi(dep["name"], get)
        if dep["eco"] == "crates":
            return versions.crates(dep["name"], get)
        if dep["eco"] == "cdn":
            return versions.npm(dep["name"], get)
        if dep["eco"] == "docker":
            return {"postgres": lambda: versions.eol("postgresql", get), "mysql": lambda: versions.eol("mysql", get), "mariadb": lambda: versions.eol("mariadb", get), "mongo": lambda: versions.eol("mongodb", get), "redis": lambda: versions.eol("redis", get)}[dep["name"]]()
    except Exception:  # noqa: BLE001
        return None
    return None


def analyze(root, get=versions._get):
    """依存ごとに最新版を引き、古いものに印を付ける。"""
    cache = {}
    out = []
    for dep in scan(root):
        key = (dep["eco"], dep["name"])
        if key not in cache:
            cache[key] = latest_of(dep, get)
        dep = dict(dep, latest=cache[key])
        cur = dep["spec"]
        dep["outdated"] = bool(dep["latest"] and cur and versions.is_newer(dep["latest"], cur))
        dep["major"] = bool(dep["outdated"] and (versions.parse(dep["latest"]) or (0,))[0] > (versions.parse(cur) or (0,))[0])
        out.append(dep)
    return out


def _bump_spec(spec, latest):
    """^1.2.3 → ^<latest>、~1.2.3 → ~<latest>、1.2.3 / ==1.2.3 → そのまま差し替え。範囲指定(>=, *, x)は触らない。"""
    m = re.match(r"^(\^|~|==|)(\d[\w.\-]*)$", spec.strip())
    return (m.group(1) + latest) if m else None


def apply(root, deps, allow_major=False):
    """package.json / requirements*.txt の版を書き換える。変更の一覧を返す。"""
    changes = []
    by_file = {}
    for d in deps:
        if d["outdated"] and (allow_major or not d["major"]) and d["eco"] in ("npm", "pypi", "cdn"):
            new = _bump_spec(d["spec"], d["latest"])
            if new:
                by_file.setdefault(d["file"], []).append((d, new))
    for path, items in by_file.items():
        text = _read(path)
        if text is None:
            continue
        orig = text
        for d, new in items:
            if d["eco"] == "cdn":
                text, c = re.subn(r"(bootstrap(?:@|/))%s" % re.escape(d["spec"]), lambda m: m.group(1) + new, text)
            elif d["eco"] == "npm":
                pat = r'("%s"\s*:\s*")%s(")' % (re.escape(d["name"]), re.escape(d["spec"]))
                text, c = re.subn(pat, lambda m: m.group(1) + new + m.group(2), text)
            else:
                pat = r"(?m)^(\s*%s\s*(?:\[[^\]]*\])?\s*)%s" % (re.escape(d["name"]), re.escape(d["spec"]))
                text, c = re.subn(pat, lambda m: m.group(1) + new, text)
            if c:
                changes.append((path, d["name"], d["spec"], new))
        if text != orig:
            with open(path + ".2poem.bak", "w", encoding="utf-8", newline="") as f:
                f.write(orig)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
    return changes


def react_report(items):
    """React の整合性の点検(全世代: 15 / 16 / 17 / 18 / 19 …)。問題の文字列のリストを返す。

    - react と react-dom の主版が違う(動かない組み合わせ)
    - @types/react の主版が react と違う
    - React 18 未満で createRoot 前提の依存を使っている、などは版の事実だけを伝える
    """
    def major(spec):
        v = versions.parse(spec)
        return v[0] if v else None

    cur = {}
    for d in items:
        if d["eco"] == "npm" and d["name"] in ("react", "react-dom", "@types/react", "@types/react-dom", "react-router-dom", "react-router", "next", "react-bootstrap"):
            cur.setdefault(d["name"], d["spec"])
    out = []
    r, rd, tr = (major(cur.get(k, "")) for k in ("react", "react-dom", "@types/react"))
    if r is not None and rd is not None and r != rd:
        out.append("react %s と react-dom %s の主版が違います(同じ主版にそろえてください)" % (cur["react"], cur["react-dom"]))
    if r is not None and tr is not None and r != tr:
        out.append("@types/react %s は react %s の主版と違います" % (cur["@types/react"], cur["react"]))
    if r is not None and r < 18 and "react-router-dom" in cur and (major(cur["react-router-dom"]) or 0) >= 7:
        out.append("react-router-dom %s は React 18 以上が前提です(react %s)" % (cur["react-router-dom"], cur["react"]))
    if r is not None and r < 16:
        out.append("react %s は Hooks 以前の版です。16.8 以上への更新を検討してください" % cur["react"])
    return out


def restore(changes):
    """apply() が残した `.2poem.bak` から元へ戻す。戻したファイルの一覧を返す。"""
    done = []
    for path in sorted({c[0] for c in changes}):
        bak = path + ".2poem.bak"
        if os.path.exists(bak):
            with open(bak, encoding="utf-8", newline="") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            done.append(path)
    return done


def apply_verified(root, deps, command, allow_major=False, run=None):
    """版を書き換え → `command`(試験コマンド)を `root` で実行 → 失敗したら元へ戻す。(変更, 試験の終了コード, 戻したか)"""
    import subprocess

    run = run or (lambda cmd, cwd: subprocess.call(cmd, shell=True, cwd=cwd))
    changes = apply(root, deps, allow_major=allow_major)
    if not changes:
        return changes, 0, False
    code = run(command, root if os.path.isdir(root) else os.path.dirname(root) or ".")
    if code != 0:
        restore(changes)
        return changes, code, True
    return changes, 0, False


def detect_test_command(root):
    """プロジェクトの試験コマンドを推定する(見つかったものを `&&` でつなぐ)。無ければ None。"""
    base = root if os.path.isdir(root) else os.path.dirname(root) or "."
    cmds = []
    pj = os.path.join(base, "package.json")
    if os.path.exists(pj):
        try:
            with open(pj, encoding="utf-8") as f:
                scripts = (json.load(f) or {}).get("scripts") or {}
            if scripts.get("test"):
                cmds.append("npm test")
        except (OSError, ValueError):
            pass
    if os.path.exists(os.path.join(base, "manage.py")):
        cmds.append("python manage.py test")
    elif os.path.isdir(os.path.join(base, "tests")) or os.path.exists(os.path.join(base, "pytest.ini")):
        cmds.append("python -m pytest -q")
    if os.path.exists(os.path.join(base, "Cargo.toml")):
        cmds.append("cargo test")
    return " && ".join(cmds) or None
