# Change Log

All notable changes to the "pybp" extension will be documented in this file.

Check [Keep a Changelog](http://keepachangelog.com/) for recommendations on how to structure this file.

## [Unreleased]

- Python 3.9 に対応。`pybp/webagg.py` のモジュール直下アノテーション
  （`url: str | None` / `_log_path: Path | None`）は PEP 604 のため 3.9 では
  import 時に評価されて `TypeError` になっていた。他の 2 ファイルと同じく
  `from __future__ import annotations` を追加して遅延評価にした。
  あわせて `requires-python` を `>=3.10` から `>=3.9` へ。
- Initial release