# 2Poem 開発メモ

- 目的: Flask/Django/FastAPI → Rust + Poem / RPoem の骨組みへの自動変換と、上流(Python・Rust・JS・TS・React・Bootstrap・Cosmo・DB)の新版追従。`F:\2Poem`(新規 2026-11-17)。標準ライブラリのみ。
- 正本の方針は [`runo/CLAUDE.md`](https://github.com/aon-co-jp/runo)。RPoem 変換は Node.js/JS/TS/React/Bootstrap/Cosmo/手書き HTML・CSS を基本的に使わない(ユーザー指示 2026-11-17)。`frontend.py` が資産を `MIGRATION.md` に記録、`emit.py` が `open-runo-view` の SSR を返す。
- 試験: `python -m pytest -q`。生成物のコンパイル確認は `2poem convert examples/... -o OUT` → `cargo check`(RPoem は `--rpoem-path`)。
- 自動更新: `_autoupdate.py`(2FastAPI/MFastAPI と同じ流儀。`TOPOEM_NO_UPDATE=1` で停止)。リリースに `.sha256` が要る(CI が付ける)。
- 注意: PowerShell 5.1 で日本語を含むファイルを書かない。
