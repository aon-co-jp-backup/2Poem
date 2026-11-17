"""RPoem 変換の「Node.js・JavaScript・TypeScript・React・Bootstrap・WunderGraph Cosmo・手書きの HTML5/CSS3 を基本的に使わない」方針の移行レポート。

画面まわりの資産(package.json・.js/.ts/.tsx・.css・テンプレート HTML・Cosmo の設定)は **コピーしない**。何があって、RPoem の何に
置き換えるかを `MIGRATION.md` に書き出す。画面は RPoem の `open-runo-view`(Rust の VNode ツリー)を Rust 側で描画する。
ブラウザへ届くのは Rust が生成した HTML であり、手書きの HTML・CSS・JavaScript はプロジェクトに含めない(ブラウザ自体は HTML を要る)。
"""
import os

from . import deps as depmod

# npm/PyPI の名前 → RPoem 側の置き換え先
REPLACE = {
    "react": "open-runo-view(Rust の VNode ツリー + SSR)",
    "react-dom": "open-runo-view(Rust の VNode ツリー + SSR)",
    "next": "RPoem のルーター + open-runo-view の SSR",
    "react-router": "RPoem の `Route::at`",
    "react-router-dom": "RPoem の `Route::at`",
    "typescript": "Rust(型は Rust の型で表す)",
    "ts-node": "Rust",
    "tsx": "Rust",
    "bootstrap": "open-runo-view で組む(スタイルは Rust 側で指定。素の CSS は移植しない)",
    "react-bootstrap": "open-runo-view で組む",
    "bootstrap-icons": "Rust 側で描画(画像・SVG は Rust から配信)",
    "express": "RPoem(open-runo-router)",
    "koa": "RPoem(open-runo-router)",
    "webpack": "不要(Rust の通常のビルド)",
    "vite": "不要(Rust の通常のビルド)",
    "esbuild": "不要",
    "jquery": "open-runo-view",
    "axios": "RPoem の Connect/gRPC クライアント(open-runo-connect-client)",
}
COSMO = "RPoem のゲートウェイ/フェデレーション(open-runo-gateway・open-runo-federation)。WunderGraph Cosmo のルーターは使わない"

EXT_KIND = {
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript(JSX)",
    ".ts": "TypeScript", ".tsx": "TypeScript(TSX)",
    ".css": "CSS", ".scss": "CSS(SCSS)", ".sass": "CSS(Sass)", ".less": "CSS(Less)",
    ".html": "HTML", ".htm": "HTML", ".jinja": "テンプレート", ".jinja2": "テンプレート", ".j2": "テンプレート",
}
SKIP = {"node_modules", "venv", ".venv", ".git", "target", "__pycache__", "dist", "build", "site-packages"}


def scan_frontend(root):
    """画面まわりのファイルと依存を集める。{"files": {種別: [パス]}, "deps": [...], "cosmo": [...]}"""
    files, cosmo = {}, []
    if os.path.isfile(root):
        return {"files": files, "deps": [], "cosmo": cosmo}
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for fn in fs:
            p = os.path.join(d, fn)
            ext = os.path.splitext(fn)[1].lower()
            if fn == "package.json":
                files.setdefault("Node.js(package.json)", []).append(p)
            elif ext in EXT_KIND:
                files.setdefault(EXT_KIND[ext], []).append(p)
            if fn in ("wundergraph.config.ts", "wundergraph.config.json", "cosmo.yaml", "graph.yaml", "router.yaml") or "cosmo" in fn.lower():
                cosmo.append(p)
    items = [x for x in depmod.scan(root) if x["eco"] in ("npm", "cdn")]
    for x in items:
        if x["kind"] == "cosmo" and x["file"] not in cosmo:
            cosmo.append(x["file"])
    return {"files": files, "deps": items, "cosmo": cosmo}


def render_report(found, root):
    """MIGRATION.md の本文。何も無ければ None。"""
    files, items, cosmo = found["files"], found["deps"], found["cosmo"]
    if not files and not items and not cosmo:
        return None
    rel = lambda p: os.path.relpath(p, root).replace("\\", "/")  # noqa: E731
    L = ["# 移行レポート(RPoem 向け)", "",
         "2Poem は RPoem への変換で、**Node.js・JavaScript・TypeScript・React・Bootstrap・WunderGraph Cosmo・手書きの HTML5/CSS3 を基本的に使いません**。",
         "下の資産はコピーしていません。画面は Rust(`open-runo-view`)で書き直してください。ブラウザへ届く HTML は Rust が生成します。", ""]
    if files:
        L += ["## 見つかった画面まわりのファイル(コピーしていません)", ""]
        for kind, ps in sorted(files.items()):
            L.append("- %s: %d 件" % (kind, len(ps)))
            for p in ps[:5]:
                L.append("  - `%s`" % rel(p))
            if len(ps) > 5:
                L.append("  - …ほか %d 件" % (len(ps) - 5))
        L.append("")
    if items:
        L += ["## 依存の置き換え先", "", "| 依存 | 版 | 置き換え先 |", "|---|---|---|"]
        seen = set()
        for x in items:
            if x["name"] in seen:
                continue
            seen.add(x["name"])
            to = COSMO if x["kind"] == "cosmo" else REPLACE.get(x["name"].lower(), "Rust(該当する RPoem の機能へ)")
            L.append("| %s | %s | %s |" % (x["name"], x["spec"] or "-", to))
        L.append("")
    if cosmo:
        L += ["## WunderGraph Cosmo", "", "- " + COSMO, "- 見つかった設定: " + ", ".join("`%s`" % rel(p) for p in cosmo[:6]), ""]
    L += ["## 注意", "", "- 画面を返す Python のハンドラは、`open-runo-view` で描画する骨組み(`TODO`)に変換しています。見た目は手で移してください。",
          "- 手書きの CSS は移植しません。レイアウトとスタイルは Rust 側の仕様として表します。", ""]
    return "\n".join(L)
