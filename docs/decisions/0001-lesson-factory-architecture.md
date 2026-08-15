# ADR-0001 — Nextbridge Lesson Factory 분리 아키텍처

- 상태: Accepted
- 결정일: 2026-08-15

## 맥락

교안의 교육성·시각 품질·현장 복구 레퍼토리를 보존하면서 반복적인 구조 검사를 자동화해야 한다. 대량 생성이 아니라 WIP=1과 단계별 Gate가 목표다. 공개 저장소에는 권리·개인정보 위험이 없는 코드·계약·fixture만 둔다.

## 결정

1. `emotigom/nextbridge-lesson-factory`를 독립 public pipeline repo로 둔다.
2. Notion은 교육 요구·결정 기록의 SSOT, Git의 course/release manifest·hash·Gate report는 기계 SSOT로 둔다.
3. PR은 changed-only Fast QA, candidate/release는 Full QA를 강제한다.
4. 실제 원본·학교자료·권리 불명 PPTX/이미지/폰트·민감 증거는 public Git에 저장하지 않는다.
5. GitHub-hosted standard runner에서 구조 QA·패키징·회귀를 수행한다.
6. Workers Static Assets는 대시보드·공개 정적문서 제공에 사용하고 Worker 실행은 `/api/*`로 제한한다.
7. 승인 바이너리는 R2 Standard의 `courses/{courseId}/{version}/{sha256}/{filename}` immutable key로 저장한다. `latest.json`만 포인터다.
8. 자동 QA는 수정기가 아니다. 실패 시 non-zero 종료하고 원본은 그대로 둔다.
9. 실제 Windows PowerPoint, 학교망·브라우저·폰트·프로젝터·인쇄, 비저자 리허설, 학생 파일럿은 사람 Gate로 남긴다.

## 결과

- classroom-kit의 공개 수업 안내와 factory의 CI/배포 권한·실패 반경이 분리된다.
- 권리 불명 바이너리가 public history에 들어갈 위험을 줄인다.
- Worker가 LibreOffice/PowerPoint 역할을 대신하는 잘못된 최적화를 막는다.
- 두 번째 교안은 현재 WIP가 `FIELD_READY` 이상이 될 때까지 차단한다.

## 비목표

- CI에서 LLM/이미지 생성
- larger runner
- Workers Paid/Containers
- PR에서 production secret 사용
- 자동으로 교육적 사실성·심리 안전·강사 자연스러움을 PASS 처리
