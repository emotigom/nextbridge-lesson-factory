#!/usr/bin/env bash
set -euo pipefail
python3 -m unittest discover -s tests -v
python3 tools/lessonctl/lessonctl.py budget check
python3 tools/lessonctl/lessonctl.py qa fast --course feed-why --json out/gate-report-fast.json
python3 tools/lessonctl/lessonctl.py qa full --course feed-why --json out/gate-report-full.json
node --check worker/src/index.js
