import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from topoem import deps, detect, emit, extract, frontend, versions  # noqa: E402

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


def routes_of(name):
    r, w, fws, py2 = extract.extract_project(os.path.join(EX, name))
    return r, w, fws, py2


def test_flask_routes_and_param_types():
    r, _, fws, _ = routes_of("flask_app.py")
    assert fws == ["flask"]
    by = {x.handler: x for x in r}
    assert by["item"].path == "/items/:item_id" and by["item"].methods == ["get", "delete"]
    assert by["item"].params[0].rust == "i64"
    assert by["upload"].path == "/users/:name/files/*rest" and by["upload"].methods == ["post"]


def test_fastapi_types_from_annotations():
    r, _, fws, _ = routes_of("fastapi_app.py")
    assert fws == ["fastapi"]
    by = {x.handler: x for x in r}
    assert by["read_item"].params[0].rust == "i64"
    assert [p.rust for p in by["set_score"].params] == ["String", "f64"]


def test_django_paths_regex_and_class_views():
    r, _, fws, _ = routes_of("django_proj")
    assert "django" in fws
    paths = {x.handler: x for x in r}
    assert paths["legacy"].path == "/legacy/:pk" and paths["legacy"].params[0].rust == "i64"
    assert paths["Hello"].methods == ["get", "post"]
    assert paths["home"].returns == "html"


def test_python2_is_converted_and_warned():
    r, w, fws, py2 = routes_of("py2_app.py")
    assert py2 and any("Python 2" in x for x in w)
    assert r and r[0].path == "/old/:n"


def test_py2_to_py3_fixes():
    out, n, _ = detect.py2_to_py3('print "a", 1\ntry:\n    pass\nexcept ValueError, e:\n    raise KeyError, "x"\nd.iteritems()\n')
    assert 'print("a", 1)' in out and "except ValueError as e:" in out and 'raise KeyError("x")' in out and ".items()" in out and n >= 4


def test_choose_target():
    assert emit.choose_target(["django"]) == "rpoem"
    assert emit.choose_target(["flask"]) == "poem"
    assert emit.choose_target(["fastapi", "flask"]) == "poem"


def test_poem_output_shape():
    r, _, _, _ = routes_of("flask_app.py")
    warn = []
    text, _ = emit.render_main(r, "poem", warn)
    assert "use poem::" in text and "Path(item_id): Path<i64>" in text
    assert '.at("/items/:item_id", get(item).delete(item_delete))' in text
    assert "Path((name, rest)): Path<(String, String)>" in text


def test_rpoem_output_has_no_js_html_css_and_uses_view():
    r, _, _, _ = routes_of("django_proj")
    warn = []
    text, _ = emit.render_main(r, "rpoem", warn)
    assert "open_runo_view::ssr::render_page" in text
    low = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//")).lower()  # コメントは除く
    for bad in ("<script", "<style", "<link", "bootstrap", "react", "node"):
        assert bad not in low, bad


def test_rpoem_patch_warns(tmp_path):
    src = tmp_path / "a.py"
    src.write_text('from flask import Flask\napp = Flask(__name__)\n@app.route("/x", methods=["PATCH"])\ndef x():\n    return {"a": 1}\n', encoding="utf-8")
    r, _, _, _ = extract.extract_project(str(src))
    warn = []
    text, _ = emit.render_main(r, "rpoem", warn)
    assert any("PATCH" in w for w in warn) and ".at(\"/x\", put(x()))" in text


def test_generate_writes_project_and_migration(tmp_path):
    r, _, _, _ = routes_of("django_proj")
    out = tmp_path / "o"
    warnings = emit.generate(r, str(out), "rpoem", rpoem_path="../RPoem", source_root=os.path.join(EX, "django_proj"))
    assert (out / "Cargo.toml").exists() and (out / "src" / "main.rs").exists()
    rep = (out / "MIGRATION.md").read_text(encoding="utf-8")
    assert "react" in rep and "typescript" in rep and "Cosmo" in rep
    assert any("MIGRATION.md" in w for w in warnings)
    # package.json / js / html はコピーされない
    assert not list(out.rglob("package.json")) and not list(out.rglob("*.js")) and not list(out.rglob("*.html"))


def fake_get(url, timeout=15):
    if "pypi.org" in url:
        return {"info": {"version": "9.9.9"}}
    if "registry.npmjs.org" in url:
        return {"version": "19.0.0"}
    if "crates.io" in url:
        return {"crate": {"max_stable_version": "3.9.0"}}
    if "endoflife.date" in url:
        return [{"latest": "17.2"}]
    return {"tag_name": "v1.99.0"}


def test_versions_fetch_with_fake_network():
    latest, errors = versions.fetch(fake_get)
    assert not errors
    assert latest["react"] == "19.0.0" and latest["poem"] == "3.9.0" and latest["python"] == "17.2" and latest["rust"] == "1.99.0"
    assert latest["bootstrap"] == "19.0.0" and latest["cosmo-cli"] == "19.0.0"
    assert versions.poem_version(fake_get) == "3.9.0"
    assert versions.drift({"react": "18.0.0"}, {"react": "19.0.0", "django": "9.9.9"}) == [("django", None, "9.9.9"), ("react", "18.0.0", "19.0.0")]


def test_deps_detect_analyze_apply(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^17.0.2", "react-dom": "^18.2.0", "bootstrap": "5.1.0", "pg": "^8.0.0", "@wundergraph/sdk": "^0.1.0"}, "devDependencies": {"typescript": "^4.9.5"}}), encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("Django==3.2.0\nflask>=2.0\npsycopg2-binary==2.9.0\n", encoding="utf-8")
    (tmp_path / "t.html").write_text('<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css">', encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services:\n  db:\n    image: postgres:13\n", encoding="utf-8")
    kinds = {(d["name"], d["kind"]) for d in deps.scan(str(tmp_path))}
    assert ("react", "react") in kinds and ("typescript", "typescript") in kinds and ("bootstrap", "bootstrap") in kinds
    assert ("@wundergraph/sdk", "cosmo") in kinds and ("pg", "db") in kinds and ("psycopg2-binary", "db") in kinds and ("postgres", "db") in kinds
    items = deps.analyze(str(tmp_path), fake_get)
    assert any(d["name"] == "react" and d["outdated"] and d["major"] for d in items)
    assert any("react 17" in m or "react ^17" in m for m in deps.react_report(items))  # react と react-dom の主版違い
    # マイナー/パッチのみ既定: 主版が上がるものは触らない
    assert deps.apply(str(tmp_path), items) == []
    ch = deps.apply(str(tmp_path), items, allow_major=True)
    assert any(c[1] == "react" and c[3] == "^19.0.0" for c in ch)
    assert (tmp_path / "package.json.2poem.bak").exists()
    assert "5.0.2" not in (tmp_path / "t.html").read_text(encoding="utf-8")
    assert "Django==9.9.9" in (tmp_path / "requirements.txt").read_text(encoding="utf-8")


def test_frontend_report_none_when_no_frontend(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert frontend.render_report(frontend.scan_frontend(str(tmp_path)), str(tmp_path)) is None


def test_open_cpu_is_in_generated_projects_by_default(tmp_path):
    r, _, _, _ = routes_of("flask_app.py")
    out = tmp_path / "a"
    emit.generate(r, str(out), "poem")
    assert "open-cpu" in (out / "Cargo.toml").read_text(encoding="utf-8")
    assert "open_cpu::runtime_report()" in (out / "src" / "main.rs").read_text(encoding="utf-8")
    out2 = tmp_path / "b"
    emit.generate(r, str(out2), "poem", open_cpu=False)
    assert "open-cpu" not in (out2 / "Cargo.toml").read_text(encoding="utf-8")
    assert "open_cpu" not in (out2 / "src" / "main.rs").read_text(encoding="utf-8")


def test_apply_verified_restores_on_failure(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}), encoding="utf-8")
    items = deps.analyze(str(tmp_path), fake_get)
    ch, code, restored = deps.apply_verified(str(tmp_path), items, "x", allow_major=True, run=lambda cmd, cwd: 1)
    assert ch and code == 1 and restored
    assert json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))["dependencies"]["react"] == "^18.0.0"
    items = deps.analyze(str(tmp_path), fake_get)
    ch, code, restored = deps.apply_verified(str(tmp_path), items, "x", allow_major=True, run=lambda cmd, cwd: 0)
    assert ch and code == 0 and not restored
    assert json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))["dependencies"]["react"] == "^19.0.0"


def test_detect_test_command(tmp_path):
    assert deps.detect_test_command(str(tmp_path)) is None
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}), encoding="utf-8")
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text("", encoding="utf-8")
    assert deps.detect_test_command(str(tmp_path)) == "npm test && python manage.py test && cargo test"


def _ported(tmp_path, src):
    f = tmp_path / "a.py"
    f.write_text(src, encoding="utf-8")
    r, _, _, _ = extract.extract_project(str(f))
    return {x.handler: x for x in r}


def test_simple_bodies_are_ported(tmp_path):
    by = _ported(tmp_path, '''from flask import Flask, jsonify
app = Flask(__name__)
@app.route("/ping")
def ping():
    """doc"""
    return {"ok": True, "n": 1, "tags": ["a"], "none": None}
@app.route("/hello/<name>")
def hello(name):
    return jsonify({"hello": name, "q": "a\\"b"})
@app.route("/t")
def t():
    return "plain"
@app.route("/c/<int:a>")
def c(a):
    return {"r": a * 2}
@app.route("/m")
def m():
    x = 1
    return {"x": x}
''')
    assert by["ping"].ported == '{"ok": true, "n": 1, "tags": ["a"], "none": null}' and by["ping"].ported_kind == "json"
    assert by["hello"].ported == '{"hello": name, "q": "a\\"b"}'
    assert by["t"].ported == '"plain"' and by["t"].ported_kind == "text"
    assert by["c"].ported == "" and by["m"].ported == ""  # 計算・複数文は自動では移植しない(TODO のまま)
    text, _ = emit.render_main(list(by.values()), "poem", [])
    assert 'Json(json!({"ok": true' in text and '"plain".to_string()' in text and "TODO" in text
    rtext, _ = emit.render_main(list(by.values()), "rpoem", [])
    assert "serde_json::json!({\"ok\": true" in rtext
