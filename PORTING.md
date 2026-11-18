# 2Poem 開発メモ

- 目的: Flask/Django/FastAPI → Rust + Poem / RPoem の骨組みへの自動変換と、上流(Python・Rust・JS・TS・React・Bootstrap・Cosmo・DB)の新版追従。`F:\2Poem`(新規 2026-11-17)。標準ライブラリのみ。
- 正本の方針は [`runo/CLAUDE.md`](https://github.com/aon-co-jp/runo)。RPoem 変換は Node.js/JS/TS/React/Bootstrap/Cosmo/手書き HTML・CSS を基本的に使わない(ユーザー指示 2026-11-17)。`frontend.py` が資産を `MIGRATION.md` に記録、`emit.py` が `open-runo-view` の SSR を返す。
- 試験: `python -m pytest -q`。生成物のコンパイル確認は `2poem convert examples/... -o OUT` → `cargo check`(RPoem は `--rpoem-path`)。
- 自動更新: `_autoupdate.py`(2FastAPI/MFastAPI と同じ流儀。`TOPOEM_NO_UPDATE=1` で停止)。リリースに `.sha256` が要る(CI が付ける)。
- 注意: PowerShell 5.1 で日本語を含むファイルを書かない。

## お引越し・再開用メッセージ
`F:\2Poem` を開き、`python -m pytest -q` と `python -m topoem scan examples/flask_app.py` で動作確認。未了は README の「未了」を参照。

## 2026-11-17 追記 / Addendum (v0.1.1)
**日本語**: v0.1.1 = 生成物へ open-cpu 同梱(`--no-open-cpu`で外す)、`deps --apply --verify "<試験>"`(失敗時は`.2poem.bak`から自動復元)。aruaru-llm は VPS で推論が遅く(GPT-2 で60秒超)共有基盤方針にも反するため**同梱しない**。RMojo の更新機能は WSL(Ubuntu)で実リリース v0.4.3 の tar.gz を取得・SHA-256 検証・置換まで成功。**未了**: macOS/Android/iOS での更新試験、利用者自身の Flask/Django/React 構成の自動アップグレード(今は`deps --apply`のみ)、業務ロジックの自動移植、生成 RPoem プロジェクトの CI 確認、PyPI 公開(将来対応)。
**再開用メッセージ**: 「`F:\2Poem` と `F:\runo` を開き、`python -m pytest -q`(20件)で確認。PORTING.md 2026-11-17 追記の未了を続けて完成させて。完成したらコミット・push・VPS反映。」
**English**: v0.1.1 bundles open-cpu into generated projects (`--no-open-cpu` to opt out) and adds `deps --apply --verify "<tests>"` (restores from `.2poem.bak` on failure). aruaru-llm is intentionally NOT bundled (too slow on the VPS, and against the shared-base policy). The RMojo updater was verified on WSL Ubuntu against the real v0.4.3 tar.gz (download, SHA-256, replace). **Open**: update tests on macOS/Android/iOS, auto-upgrade of users' own Flask/Django/React stacks, automatic business-logic porting, CI for generated RPoem projects, PyPI publication (deferred).
**Resume message**: "Open `F:\2Poem` and `F:\runo`, run `python -m pytest -q` (20 tests), then continue the open items in the 2026-11-17 addendum of PORTING.md; when done, commit, push and deploy to the VPS."

## 2026-11-18 追記 / Addendum (v0.1.2)
**日本語**: v0.1.2 = `2poem deps <パス> --apply --verify auto`(npm test / manage.py test / pytest / cargo test を自動判定し、失敗したら元へ自動復元。実際に失敗する試験で復元を確認)。生成した RPoem プロジェクト(Django 例)の `cargo check` を CI に追加(RPoem の兄弟依存 open-web-server・RS-SmartTCP・open-raid-z・open-cpu・RS-JSON を checkout。RPoem 側の兄弟依存が増えると落ちるので追加が要る)。**未了**: aruaru-llm 同梱(VPS で遅く見送り)、macOS/Android/iOS の更新試験、業務ロジックの自動移植、PyPI公開(将来対応)。**再開用メッセージ**: 「`F:\2Poem` を開き `python -m pytest -q`(21件)で確認、本ファイルの未了を続けて完成させて。完成したらコミット・push。」
**English**: v0.1.2 adds `2poem deps <path> --apply --verify auto` (detects npm test / manage.py test / pytest / cargo test; restores the originals on failure, verified with a really failing test). CI now runs `cargo check` on a generated RPoem project (Django example), checking out RPoem's sibling path dependencies (open-web-server, RS-SmartTCP, open-raid-z, open-cpu, RS-JSON); new sibling deps in RPoem will break it until added. **Open**: aruaru-llm bundling (skipped), updater tests on macOS/Android/iOS, automatic business-logic porting, PyPI (deferred). **Resume message**: "Open `F:\2Poem`, run `python -m pytest -q` (21 tests), continue the open items above; commit and push when done."
