"""上流の最新版の取得(標準ライブラリのみ)。Python / Rust / Node / TypeScript / React / Bootstrap / DB / Django / Flask / FastAPI / Poem / RPoem / WunderGraph Cosmo。

取得できなかった項目は含めない(呼び出し側は前回の値や `compat.json` の固定値へ戻す)。`fetch` は差し替え可能(試験用)。
"""
import json
import os
import urllib.request

UA = "2poem-versions"


def _get(url, timeout=15):
    h = {"User-Agent": UA, "Accept": "application/json"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and "api.github.com" in url:
        h["Authorization"] = "Bearer " + tok
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def pypi(name, get=_get):
    return get("https://pypi.org/pypi/%s/json" % name)["info"]["version"]


def npm(name, get=_get):
    return get("https://registry.npmjs.org/%s/latest" % name.replace("/", "%2F"))["version"]


def crates(name, get=_get):
    return get("https://crates.io/api/v1/crates/%s" % name)["crate"]["max_stable_version"]


def eol(product, get=_get):
    """endoflife.date: 製品の最新リリース(DB・Node・Python など)。"""
    return get("https://endoflife.date/api/%s.json" % product)[0]["latest"]


def github_release(repo, get=_get):
    return get("https://api.github.com/repos/%s/releases/latest" % repo)["tag_name"].lstrip("v")


SOURCES = {
    "python": lambda g: eol("python", g),
    "rust": lambda g: github_release("rust-lang/rust", g),
    "node": lambda g: eol("nodejs", g),
    "typescript": lambda g: npm("typescript", g),
    "react": lambda g: npm("react", g),
    "bootstrap": lambda g: npm("bootstrap", g),
    "postgresql": lambda g: eol("postgresql", g),
    "mysql": lambda g: eol("mysql", g),
    "sqlite": lambda g: eol("sqlite", g),
    "django": lambda g: pypi("django", g),
    "flask": lambda g: pypi("flask", g),
    "fastapi": lambda g: pypi("fastapi", g),
    "starlette": lambda g: pypi("starlette", g),
    "poem": lambda g: crates("poem", g),
    "cosmo-cli": lambda g: npm("wgc", g),  # WunderGraph Cosmo の CLI
    "rpoem": lambda g: github_release("aon-co-jp/RPoem", g),
}


def fetch(get=_get, only=None):
    """{名前: 最新版} を返す。失敗した項目は入らない。(失敗の理由は `errors`)"""
    out, errors = {}, {}
    for k, fn in SOURCES.items():
        if only and k not in only:
            continue
        try:
            out[k] = fn(get)
        except Exception as e:  # noqa: BLE001
            errors[k] = str(e)
    return out, errors


def parse(v):
    parts = []
    for p in str(v).lstrip("v^~>=< ").split("."):
        digits = "".join(c for c in p if c.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts + [0] * (3 - len(parts)))[:3] if parts else None


def is_newer(latest, current):
    a, b = parse(latest), parse(current)
    return bool(a and b and a > b)


def drift(known, latest):
    """前回の値(compat.json など)と最新の差。[(名前, 旧, 新)]"""
    return [(k, known.get(k), v) for k, v in sorted(latest.items()) if known.get(k) != v]


def poem_version(get=_get, fallback="3"):
    """生成する Cargo.toml に書く poem の版(最新の安定版。取得できなければ固定値)。"""
    try:
        return crates("poem", get)
    except Exception:  # noqa: BLE001
        return fallback
