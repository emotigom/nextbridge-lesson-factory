# Sample PR QA Report

**Course:** feed-why  
**PR policy:** change-impact aware  
**Automated technical result:** PASS  
**Stage:** TECH_QA  
**Release decision:** HOLD

| Gate | 결과 | 근거 |
|---|---|---|
| course schema | PASS | required fields/type/state valid |
| WIP=1 | PASS | active course 1개 |
| source lock | PASS | v0.4 frozen SHA contract matches |
| private package inventory | PASS | manifest assets 15/15 size/SHA |
| embedded validator | PASS | `INTEGRITY_PASS …; RELEASE_HOLD` |
| runtime regression | PASS | 34/34, matrix 108/108, deterministic report SHA |
| prototype contract | PASS | 5 slides/5 notes, QA checks 8/8 |
| render evidence | PASS | pixel regression 5/5, overflow 0; **font approval은 아님** |
| PPTX structure | PASS | hidden/orphan/placeholder/DrawingML fatal issue 0 |
| font portability | HOLD | NanumBarunGothic/NanumSquare referenced, embedded font parts 0 |
| public-repo safety | PASS | actual private ZIP/PPTX/HTML not committed |
| SSOT sync | HOLD | observed Notion metadata still points to prototype v0.3 |
| manual gates | HOLD | browser/PowerPoint/font/rehearsal/student pilot pending |

**Promotion blockers:** `SSOT_STALE_METADATA`, `QUALITY_NOT_SCORED`, `RIGHTS_UNVERIFIED`, `MANUAL_GATES_PENDING`.

이 보고서는 자동 기술 QA의 `PASS`를 출시 승인으로 해석하지 않는다. `INTEGRITY_PASS ≠ RELEASE_APPROVED`다.
