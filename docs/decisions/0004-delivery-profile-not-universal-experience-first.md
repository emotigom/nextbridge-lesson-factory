# ADR-0004 — 수업 레퍼토리를 experience-first 하나로 고정하지 않는다

## 상태

Accepted

## 배경

Factory의 초기 content-design gate는 clean-room 수업에서 다음 두 규칙을 사실상 전역 기본으로 강제했다.

- 첫 학생 행동이 3분 이내에 시작해야 함
- 보호 개념은 학생이 현상을 먼저 경험한 뒤에만 studentText에 등장해야 함

이 규칙은 탐구형·발견형 수업에는 유효하지만, 제작 도구를 함께 따라 만드는 현장 수업에는 과도하게 편향될 수 있다.

특히 강사가 주제와 필요한 이론을 짧게 설명하고, 동영상/완성 예시를 보여준 뒤, 작업을 설명하고 학생과 같은 화면에서 guided practice를 진행하는 수업에서는 개념이 실습보다 먼저 나오는 것이 정상적이다. 이 패턴을 억지로 experience-first로 바꾸면 강사가 교안의 의도를 읽기 어렵고, 학생이 실제 도구를 다루는 시간이 늦어지며, 결과물이 추상적인 토의·기획 중심으로 흐를 수 있다.

## 결정

Course Map에 선택 가능한 `deliveryProfile`을 추가한다.

- `experience-first`
- `guided-build`
- `explain-practice`

Factory의 첫 행동 deadline, 연속 LEARN 허용량, 개념 도입 타이밍은 `policies/delivery-profiles.json`의 선택 프로필에 따라 달라진다.

`guided-build`는 반드시 `practiceAnchor`를 가진다.

- `tool`: 학생과 강사가 실제로 사용할 핵심 도구
- `studentBuild`: 학생이 수업 중 실제로 완성할 결과물

권장 guided-build 리듬은 다음과 같다.

`주제/맥락 → 필요한 이론 → 영상 또는 완성 예시 → 작업 설명 → 함께 실습 → 자기 것으로 바꾸기 → 결과 확인`

설명 약 15분, 실습 약 20분은 대표적인 현장 리듬일 뿐 고정 시간 계약은 아니다. 차시와 주제에 따라 반복 횟수와 시간은 달라질 수 있다.

## 결과

- `experience-first` 과정은 기존 3분 진입과 experience-before-concept 보호를 유지한다.
- `guided-build`는 필요한 이론을 실습 전에 제시할 수 있고 첫 실제 학생 행동 deadline을 20분으로 둔다.
- 새 교안은 상세 설계 전에 deliveryProfile을 명시적으로 선택하도록 ChatGPT 시작 템플릿에서 안내한다.
- 도구 기반 guided-build 과정은 구체적 tool/studentBuild 없이 Course Map을 승인할 수 없다.
- 어떤 프로필도 교육적으로 우월한 전역 기본값으로 취급하지 않는다.

## 하지 않는 것

- 모든 수업을 guided-build로 강제하지 않는다.
- 설명 15분/실습 20분을 Hard Gate로 만들지 않는다.
- 동영상 자체를 모든 차시의 필수 요소로 기계 강제하지 않는다.
- 기존 공개 course의 역사적 설계 증거를 소급 변경하지 않는다.
