# ADR-0002 — 교육 설계 계약을 기술 QA 앞에 둔다

- 상태: Accepted
- 결정일: 2026-08-16

## 맥락

기존 Factory는 패키지 무결성, SHA lock, 오프라인 HTML, PPTX 구조, 수동 Gate를 강하게 검증한다. 반면 좋은 교안이 만들어지기 전 단계인 입력 제한, 차시별 승인, 학생 화면 언어, 경험 뒤 개념 도입, CORE/BUFFER 시간 구조는 기계 계약으로 충분히 표현되지 않았다.

실제 clean-room 제작에서 품질이 좋아진 핵심은 다음이었다.

- 과거 산출물의 문장·레이아웃·활동을 새 설계로 역류시키지 않음
- 전체 차시 상위 구조를 먼저 승인
- 한 차시씩 상세 설계하고 승인 전 다음 차시를 만들지 않음
- PPTX/HTML보다 storyboard를 먼저 확정
- 학생 경험 → 질문 → 작은 행동 → 결과 관찰 → 개념 → 다시 행동 → 자기 말로 정리
- 학생 화면과 교사용 설명 분리
- CORE와 BUFFER 분리
- 20항목·100점 rubric으로 영역별 개선

## 결정

1. `contracts/clean-room-source.schema.json`으로 허용 입력과 과거 산출물 복사 금지를 표현한다.
2. `contracts/course-map.schema.json`으로 전체 차시 질문·핵심 경험·최소 산출물을 먼저 잠근다.
3. `contracts/storyboard.schema.json`으로 슬라이드의 우선순위, 역할, 학생 화면, 학생 행동, 교사 대본, 예상 반응, 복구 문장, 연결, 시간을 분리한다.
4. `policies/student-language.json`은 학생 화면에만 적용한다. QA·SHA 같은 기술 언어를 저장소 전체에서 금지하지 않는다.
5. `policies/concept-order.json`은 “경험 뒤 개념 도입”이라는 전역 원칙만 가진다. 실제 보호 개념어 목록은 각 design bundle의 `concept-policy.json`이 가지며 `contracts/concept-order.schema.json`을 따른다. 해당 개념은 slide가 `conceptsIntroduced`로 선언하기 전 studentText에 등장하면 hard fail한다.
6. BUFFER는 새로운 필수 개념을 도입할 수 없다.
7. 첫 학생 행동은 수업 시작 3분 안에 와야 한다.
8. 18~22장, Teaching Beat 6~8개는 목표값이며 hard fail이 아니라 warning으로 둔다.
9. `policies/quality-rubric.json`의 20개 항목을 공식 100점 모델로 삼고 Q01/Q05/Q08/Q10/Q12/Q15/Q20을 필수 Gate로 둔다.
10. 교육적 자연스러움·학생 정서·개념 정확성의 최종 PASS는 여전히 사람이 판단한다. 자동화는 명백한 계약 위반을 차단하고 검토 지점을 좁힌다.

## 호환성

이번 변경은 현재 활성 release lifecycle과 R2/Cloudflare 배포 경로를 바꾸지 않는다. 현재 `feed-why`의 v0.4 golden fixture도 그대로 유지한다. 다만 prototype 장수/노트 수와 같은 기대값은 코드 상수가 아니라 golden contract에서 읽도록 일반화한다.

`feed-why`를 새 clean-room 기준으로 실제 migration하는 작업은 별도 PR에서 수행한다.

## 결과

Factory는 이제 두 종류의 품질을 구분한다.

1. **Content design integrity** — 좋은 수업 구조가 만들어질 조건
2. **Artifact/runtime integrity** — 만들어진 PPTX/HTML/패키지가 깨지지 않을 조건

둘 다 통과해야 다음 배포 단계로 이동할 수 있다.
