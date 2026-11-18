"""2poem convert | scan | versions | deps | update"""
import argparse
import json
import os
import sys

from . import __version__


def _convert(a):
    from . import emit, extract, versions

    routes, warnings, fws, py2 = extract.extract_project(a.path)
    target = a.target if a.target != "auto" else emit.choose_target(fws)
    pv = a.poem_version or versions.poem_version()
    out = a.output or (os.path.splitext(a.path)[0] if os.path.isfile(a.path) else a.path.rstrip("/\\")) + "-" + target
    if a.dry_run:
        text, _ = emit.render_main(routes, target, warnings)
        print(text)
    else:
        warnings += emit.generate(routes, out, target, name=a.name, poem_version=pv, rpoem_path=a.rpoem_path, source_root=a.path, open_cpu=not a.no_open_cpu)
    print("// frameworks: %s | python2 files: %d | routes: %d | target: %s%s" % (", ".join(fws) or "none", len(py2), len(routes), target, "" if a.dry_run else " | wrote: " + out), file=sys.stderr)
    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    return 0 if routes else 1


def _scan(a):
    from . import extract

    routes, warnings, fws, py2 = extract.extract_project(a.path)
    if a.json:
        print(json.dumps({"frameworks": fws, "python2": py2, "routes": [{"methods": r.methods, "path": r.path, "handler": r.handler, "framework": r.framework, "params": [p.name for p in r.params]} for r in routes], "warnings": warnings}, ensure_ascii=False, indent=1))
    else:
        for r in routes:
            print("%-14s %-8s %s -> %s" % (",".join(m.upper() for m in r.methods), r.framework, r.path, r.handler))
        for w in warnings:
            print("warning: " + w, file=sys.stderr)
        print("%d routes, frameworks: %s, python2 files: %d" % (len(routes), ", ".join(fws) or "none", len(py2)))
    return 0


def _versions(a):
    from . import versions

    latest, errors = versions.fetch()
    known = {}
    if a.compat and os.path.exists(a.compat):
        with open(a.compat, encoding="utf-8") as f:
            known = json.load(f).get("versions", {})
    for k, v in sorted(latest.items()):
        print("%-12s %-10s%s" % (k, v, "" if known.get(k) in (None, v) else "  (前回 %s)" % known.get(k)))
    for k, e in errors.items():
        print("warning: %s を取得できません: %s" % (k, e), file=sys.stderr)
    if a.write and a.compat:
        with open(a.compat, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"versions": {**known, **latest}}, f, indent=1, sort_keys=True)
            f.write("\n")
    return 0


def _deps(a):
    from . import deps

    items = deps.analyze(a.path)
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
    else:
        for d in items:
            mark = "MAJOR" if d["major"] else ("update" if d["outdated"] else "ok")
            print("%-10s %-6s %-30s %-14s -> %-12s %s" % (d["kind"], d["eco"], d["name"], d["spec"] or "-", d["latest"] or "?", mark))
    for msg in deps.react_report(items):
        print("react: " + msg)
    if a.apply:
        verify = deps.detect_test_command(a.path) if a.verify == "auto" else a.verify
        if a.verify == "auto":
            print("verify command: %s" % (verify or "(試験が見つからないため、検証なしで書き換えます)"))
        if verify:
            changes, code, restored = deps.apply_verified(a.path, items, verify, allow_major=a.major)
        else:
            changes, code, restored = deps.apply(a.path, items, allow_major=a.major), 0, False
        for path, name, old, new in changes:
            print("updated %s: %s %s -> %s" % (path, name, old, new))
        if restored:
            print("verify failed (exit %d): restored the original files" % code, file=sys.stderr)
            return 1
    return 0


def _update(a):
    from . import _autoupdate

    return _autoupdate.main(["--now"])


def main(argv=None):
    from ._autoupdate import maybe_start

    maybe_start()  # 起動時の自動バージョンアップ(24時間に1回、切り離して確認。TOPOEM_NO_UPDATE=1 で停止)
    ap = argparse.ArgumentParser(prog="2poem", description="Convert Flask / Django / FastAPI to Rust + Poem / RPoem; follow upstream releases.")
    ap.add_argument("--version", action="version", version="2poem " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="generate a Rust (Poem/RPoem) skeleton from a Python project or file")
    c.add_argument("path")
    c.add_argument("-o", "--output")
    c.add_argument("--target", choices=["auto", "poem", "rpoem"], default="auto", help="auto: Django -> rpoem, Flask/FastAPI -> poem")
    c.add_argument("--name", default="converted-app")
    c.add_argument("--poem-version", default=None, help="default: latest stable from crates.io")
    c.add_argument("--rpoem-path", default="../RPoem")
    c.add_argument("--no-open-cpu", action="store_true", help="do not add open-cpu (CPU feature detection) to the generated project")
    c.add_argument("--dry-run", action="store_true", help="print main.rs only")
    c.set_defaults(fn=_convert)
    s = sub.add_parser("scan", help="list routes found")
    s.add_argument("path")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=_scan)
    v = sub.add_parser("versions", help="latest versions of Python/Rust/Node/TypeScript/React/Bootstrap/DB/Django/Flask/FastAPI/Poem/RPoem/Cosmo")
    v.add_argument("--compat", default=None, help="compat.json to compare with")
    v.add_argument("--write", action="store_true", help="write the fetched versions into --compat")
    v.set_defaults(fn=_versions)
    d = sub.add_parser("deps", help="detect JS/TS/React/Bootstrap/Cosmo/DB/Python dependencies and bump them")
    d.add_argument("path")
    d.add_argument("--apply", action="store_true", help="rewrite package.json / requirements*.txt (backup: .2poem.bak)")
    d.add_argument("--verify", default=None, help="command to run after --apply (e.g. \"npm test\"; \"auto\" detects npm test / manage.py test / pytest / cargo test); on failure the original files are restored")
    d.add_argument("--major", action="store_true", help="also apply major-version bumps")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=_deps)
    u = sub.add_parser("update", help="update 2Poem itself now")
    u.set_defaults(fn=_update)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
