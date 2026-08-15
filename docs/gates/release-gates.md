# Release Gates

## 상태기계

`DRAFT → CONTENT_QA → TECH_QA → INSTRUCTOR_PILOT → FIELD_PILOT → FIELD_READY → CANONICAL`

`HOLD`는 단계가 아니라 출시 판정이다. 활성 WIP는 정확히 1개이며 `FIELD_READY` 이상 전에는 다음 교안을 활성화하지 않는다.

## RELEASE_APPROVED 필수 조건

`lessonctl release verify --require-approved`는 아래를 **모두** 검사하고 하나라도 빠지면 non-zero로 중단한다.

- `releaseDecision = APPROVED`
- stage `FIELD_READY` 이상
- SSOT `SYNCED`
- 품질점수 90/100 이상
- 품질 영역이 1개 이상 실제 기록되어 있고 어느 영역도 80점 미만 없음
- 비저자 강사 리허설 실제시간이 계획시간 ±10% 이내
- 학생 최소 산출물 완성률 85% 이상
- 저장·제출 성공률 90% 이상
- 개인정보·치명적 운영사고 0건
- 권리 상태 `VERIFIED` + public distribution 승인
- reviewer와 approvedAt 존재
- 아래 7개 사람 Gate가 모두 존재하고 `PASS`
  - `BROWSER_FILE_SMOKE`
  - `VIEWPORT_1440_900_375_812`
  - `JSON_ROUNDTRIP_PRINT`
  - `WINDOWS_POWERPOINT_SMOKE`
  - `FONT_PORTABILITY_REFLOW`
  - `INDEPENDENT_INSTRUCTOR_REHEARSAL`
  - `STUDENT_FIELD_PILOT`
- 각 수동 증거의 `subjectSha256`가 현재 source lock과 일치. HTML/PPT가 바뀌면 관련 증거는 자동으로 stale 판정
- course contract와 release manifest의 stage/releaseDecision/SSOT가 서로 일치

## 자동 Gate — 현재 구현

- source SHA/golden contract/WIP=1
- public repo의 금지 바이너리·기본 PII·secret-like literal scan
- ZIP CRC, duplicate path, path traversal, Unicode normalization collision, hidden path
- XML/SVG/RELS/Content Types parse와 내부 relationship target
- PPTX slide/note count, hidden/orphan, placeholder text, external relationship inventory
- DrawingML exponent/비정상 shadow 수치, slide bounds 밖 shape 후보
- 폰트 참조·임베딩 여부·언어 태그 inventory
- 발표자 노트 10개 필수 구역
- private v0.4 manifest asset 1:1 size/SHA
- prototype QA report subject SHA/8개 check cross-contract
- 5장 render evidence pixel 5/5 동일, overflow 0, preview SHA cross-contract
- HTML 외부 ref/network API/기본 PII scan
- runtime 상태전이 34/34와 report SHA 결정성
- release manifest asset size/SHA와 immutable R2 key
- 결정적 ZIP 2회 SHA 동일성
- PR change impact → Fast 또는 Full public QA 선택
- 월 $0 정책/larger runner/Worker 경로 architecture guard

## 반자동·후속 확장 영역

현재 구조적 후보를 만들 수 있지만 자동 PASS로 종결하지 않는 항목: 실제 렌더 기반 텍스트 overflow/clipping, 글자 밀도·최소 크기·대비, 맞춤법·사실·출처, 목표–활동–산출물–평가 매핑, 폰트 대체 reflow, QR의 사람이 의도한 목적지 의미 검토.

## 사람 전용

교육적 최종 정확성, 학생 정서·개인정보 안전, 강사 대본 자연스러움, 실제 Windows PowerPoint, 학교 브라우저·망·폰트·프로젝터·인쇄, 비저자 리허설, 학생 파일럿은 자동 PASS하지 않는다.
