# ADR-0003 — feed-why clean-room 성공본은 공개 proof와 private 상세본으로 분리한다

- 상태: Accepted
- 결정일: 2026-08-16

## 배경

`feed-why`의 기존 기계 SSOT는 5장 vertical prototype v0.4를 runtime 기준으로 추적한다. 이후 clean-room 방식으로 4차시 전체 교안, 오프라인 실습도구, 학생 활동자료, 미디어와 최종 QA가 새로 완성되었다.

새 성공본의 상세 storyboard 문장·PPTX·HTML·미디어 전체를 public MIT 저장소에 다시 공개할 필요는 없다. 반대로 GitHub가 계속 옛 시제품만 알고 있으면 새로운 제작 방식의 성공을 다음 교안에 재사용할 수 없다.

## 결정

1. `courses/feed-why/design/cleanroom-v1/design-proof.json`을 새 설계 트랙의 공개 기계 증거로 둔다.
2. 공개 proof에는 다음만 기록한다.
   - clean-room 입력 자료의 SHA-256
   - 4차시 상위 질문·핵심 경험·최소 산출물
   - 차시별 Teaching Beat/CORE/BUFFER/시간 통계
   - 20항목 rubric의 영역 점수와 총점
   - 최종 실행패키지/PPTX/실습도구/활동자료/미디어 SHA-256
   - 구조 QA 결과와 아직 필요한 수동 환경 확인
3. 상세 storyboard, 실제 PPTX/HTML/미디어, private evidence bundle은 public Git에 커밋하지 않는다.
4. `lessonctl qa`는 public proof 자체의 스키마·일관성·해시 형식·품질 합계·오프라인 QA 요약을 검증한다.
5. 기존 v0.4 `sourceLock`, golden fixture, release `HOLD`는 새 runtime candidate hydration 계약을 별도로 만들 때까지 유지한다. clean-room design 승인과 legacy runtime release 승인을 섞지 않는다.
6. 권리 상태와 실제 Windows/브라우저 수동 확인이 닫히기 전에는 public distribution을 승인하지 않는다.

## 결과

- 다음 교안은 이번 성공본의 설계 구조와 품질 기준을 재사용할 수 있다.
- public 저장소에는 상세 교안 내용과 대형 바이너리가 추가되지 않는다.
- 기존 v0.4 runtime 회귀 검사는 깨지지 않는다.
- Pipeline은 Factory의 정확한 commit SHA와 이 design proof를 묶어 실제 `feed-why` 승인 상태를 추적할 수 있다.
