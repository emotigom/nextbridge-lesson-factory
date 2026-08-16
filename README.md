# Nextbridge Lesson Factory

교안을 많이 만드는 저장소가 아니라, **한 번에 하나(WIP=1)**의 교안을 검증 가능한 상태로 만들고 Gate를 통과한 결과만 배포하기 위한 품질 엔진입니다.

## 비협상 원칙

- `DRAFT → CONTENT_QA → TECH_QA → INSTRUCTOR_PILOT → FIELD_PILOT → FIELD_READY → CANONICAL`
- 현재 활성 교안이 `FIELD_READY` 이상이 되기 전에는 다음 교안을 시작하지 않습니다.
- 원본 학교자료·개인정보·권리 불명 자산·실제 배포용 대형 바이너리는 public Git에 넣지 않습니다.
- 자동 QA는 파일을 몰래 고치지 않습니다. Hard Gate 실패는 non-zero exit로 중단합니다.
- `INTEGRITY_PASS`와 `RELEASE_APPROVED`는 다른 상태입니다.
- PR은 Fast QA, 승인 candidate/release는 Full QA입니다.
- Cloudflare Worker는 `/api/*`와 전달 계층에만 사용하며 LibreOffice/PowerPoint 렌더를 실행하지 않습니다.

## 교육 설계 Gate

PPTX/HTML을 만들기 전에 교육 설계 자체를 먼저 잠급니다.

1. `source-policy.json` — clean-room에서 읽어도 되는 자료와 복사 금지 범위를 고정
2. `course-map.json` — 전체 차시 질문·핵심 경험·최소 산출물을 먼저 승인
3. `storyboards/session-N.json` — 한 차시씩 상세 설계하고 사람 승인
4. `quality-score.json` — 20항목·100점 rubric과 7개 필수 항목을 기록

학생 화면은 설명보다 행동을 우선하고, `신호·가중치·다양성·새로움·안전` 같은 개념어는 해당 현상을 경험한 뒤에만 처음 노출합니다. BUFFER에는 새로운 필수 개념을 넣지 않습니다.

설계 bundle 예시는 synthetic fixture로만 공개 저장소에 둡니다.

```bash
python3 tools/lessonctl/content_design.py check \
  --path fixtures/design/clean-room-pass \
  --json out/content-design-report.json
```

이 검사는 clean-room 입력 정책, 차시 지도 잠금, 첫 학생 행동 시점, CORE/BUFFER 시간, 학생 화면의 내부 QA/보고체 문구, 경험 전 개념어 노출, 100점 rubric 합계와 필수 항목을 검사합니다. 슬라이드 수 18~22장과 Teaching Beat 6~8개는 교육 흐름을 망치지 않도록 hard fail이 아니라 warning입니다.

## 빠른 실행

```bash
python3 tools/lessonctl/content_design.py check --path fixtures/design/clean-room-pass
python3 tools/lessonctl/lessonctl.py intake courses/feed-why/course.yaml
python3 tools/lessonctl/lessonctl.py qa fast --course feed-why --json out/gate-report.json
python3 tools/lessonctl/lessonctl.py qa full --course feed-why --json out/gate-report-full.json
python3 -m unittest discover -s tests -v
python3 tools/lessonctl/lessonctl.py budget check
node --check worker/src/index.js
```

현재 `sourceLock`에 고정된 private 패키지를 로컬에서 재검증할 때만 실제 경로를 넘깁니다. 파일명이나 장수는 코드에 고정하지 않고 golden contract가 기대값을 가집니다.

```bash
python3 tools/lessonctl/lessonctl.py qa full \
  --course feed-why \
  --private-package /path/to/current-approved-private-package.zip \
  --json out/feed-why-full-private.json
```

## 공개/비공개 경계

활성 교안의 실제 ZIP/PPTX/HTML과 학교 원본은 공개 저장소에 커밋하지 않습니다. 이 저장소에는 검증된 SHA, 기대 결과 계약, 공개 가능한 정책·스키마, synthetic fixture만 둡니다. 자세한 결정은 `docs/decisions/0001-lesson-factory-architecture.md`와 `docs/decisions/0002-content-design-contracts.md`를 참고하세요.

## R2 / Cloudflare 안전 경계

`tools/package/r2_publish.py`는 `HOLD`, FIELD_READY 미만, 품질/권리/SSOT/사람 Gate/파일럿 지표 미충족 release를 hard fail한다. 기본 실행은 dry-run이며 실제 R2 write는 production 승인과 명시적 `--execute` 없이는 수행하지 않는다. Cloudflare production 배포나 R2 write는 별도 승인 없이 실행하지 않는다.

## 수동 Gate 증거와 단계 승격

수동 Gate는 실제 사람이 수행하고, `lessonctl`은 그 증거가 현재 source SHA를 대상으로 했는지만 검증합니다.

```bash
./lessonctl evidence subject --course feed-why --gate BROWSER_FILE_SMOKE
./lessonctl evidence verify --course feed-why --file /secure/evidence/browser.json
./lessonctl stage check --course feed-why --to INSTRUCTOR_PILOT --evidence-dir /secure/evidence
```

실제 증거 파일은 public Git에 넣지 않습니다. main 직접 반영도 `.github/workflows/qa-main.yml`의 Full public QA를 통과해야 합니다.

대시보드 상태 파일은 수동 편집하지 않습니다. 기계 SSOT에서 다시 생성하고 일치 여부를 검증합니다.

```bash
./lessonctl dashboard build --course feed-why
./lessonctl dashboard verify --course feed-why
```
