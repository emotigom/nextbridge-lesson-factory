# Manual evidence contract

수동 Gate는 사람이 수행하지만 판정 대상은 SHA로 고정한다. 브라우저·PowerPoint·폰트·리허설·학생 파일럿 결과를 자동으로 만들어 내거나 자동 PASS하지 않는다.

## 저장 경계

실제 스크린샷, 학생 파일럿 기록, 학교 환경 정보, 강사 리허설 기록은 공개 Git에 저장하지 않는다. 승인된 private R2 또는 별도 승인 저장소에 보관하고, 공개 Git에는 Gate 상태와 대상 SHA만 남긴다.

## 현재 Gate 계획

```bash
./lessonctl evidence plan --course feed-why
```

각 Gate의 현재 `subjectSha256`와 필수 실측 항목을 출력한다. 자산 SHA가 바뀌면 이전 증거는 STALE이다.

## 증거 파일

각 증거는 `contracts/manual-evidence.schema.json`을 따르며 `courseId`, `gate`, `status`, `subjectSha256`, `capturedAt`, `reviewer`, `environment`, `evidenceRefs`, 그리고 PASS일 경우 Gate별 `metrics`가 필요하다.

`subjectSha256`은 임의로 입력하지 않는다.

```bash
./lessonctl evidence subject --course feed-why --gate BROWSER_FILE_SMOKE
```

두 자산에 동시에 의존하는 Gate는 두 SHA를 고정 순서로 연결해 다시 SHA-256한 값을 subject로 사용한다.

## PASS 실측 계약

- `BROWSER_FILE_SMOKE`: Chrome PASS, Edge PASS, 두 브라우저 console error 0, `file://` PASS
- `VIEWPORT_1440_900_375_812`: 1440×900 PASS, 375×812 PASS
- `JSON_ROUNDTRIP_PRINT`: JSON 다운로드 → 새 팀 → import 모두 PASS, print preview PASS, clipping 0
- `WINDOWS_POWERPOINT_SMOKE`: open·notes·slideshow·PDF export·save/reopen PASS, recovery dialog 0
- `FONT_PORTABILITY_REFLOW`: clean machine PASS, missing glyph 0, full reflow 승인
- `INDEPENDENT_INSTRUCTOR_REHEARSAL`: planned/actual time 존재, ±10% 이내, 3분 Rescue PASS
- `STUDENT_FIELD_PILOT`: 최소 산출물 완성률 ≥85%, 저장·제출 ≥90%, 개인정보·치명 사고 0

문자열 `status: PASS`만으로는 통과하지 않는다. 위 실측값이 빠지거나 기준 미달이면 `lessonctl evidence verify`가 non-zero로 실패한다.

## 검증

```bash
./lessonctl evidence verify --course feed-why --file /secure/evidence/browser.json
```

증거 디렉터리를 이용해 다음 단계 승격 가능 여부만 확인한다. 이 명령은 `course.yaml`을 수정하지 않는다.

```bash
./lessonctl stage check \
  --course feed-why \
  --to INSTRUCTOR_PILOT \
  --evidence-dir /secure/evidence
```

정상 단계는 한 단계씩만 이동한다. 단계 건너뛰기와 역행은 실패한다.
