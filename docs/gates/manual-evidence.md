# Manual evidence contract

수동 Gate는 사람이 수행하지만 판정 대상은 SHA로 고정한다. 브라우저·PowerPoint·폰트·리허설·학생 파일럿 결과를 자동으로 만들어 내거나 자동 PASS하지 않는다.

## 저장 경계

실제 스크린샷, 학생 파일럿 기록, 학교 환경 정보, 강사 리허설 기록은 공개 Git에 저장하지 않는다. 승인된 private R2 또는 별도 승인 저장소에 보관하고, 공개 Git에는 Gate 상태와 대상 SHA만 남긴다.

## 증거 파일

각 증거는 `contracts/manual-evidence.schema.json`을 따른다. 필수 항목은 `courseId`, `gate`, `status`, `subjectSha256`, `capturedAt`, `reviewer`, `environment`, `evidenceRefs`다.

`subjectSha256`은 임의로 입력하지 않는다.

```bash
./lessonctl evidence subject --course feed-why --gate BROWSER_FILE_SMOKE
```

두 자산에 동시에 의존하는 Gate는 두 SHA를 고정 순서로 연결해 다시 SHA-256한 값을 subject로 사용한다. 어느 한 자산이라도 바뀌면 기존 증거는 자동으로 STALE 취급한다.

## 검증

```bash
./lessonctl evidence verify --course feed-why --file /secure/evidence/browser.json
```

증거 디렉터리를 이용해 다음 단계 승격 가능 여부만 확인할 수 있다. 이 명령은 `course.yaml`을 수정하지 않는다.

```bash
./lessonctl stage check \
  --course feed-why \
  --to INSTRUCTOR_PILOT \
  --evidence-dir /secure/evidence
```

정상 단계는 한 단계씩만 이동한다. 단계 건너뛰기와 역행은 실패한다.

- `TECH_QA → INSTRUCTOR_PILOT`: 브라우저 file://, 두 viewport, JSON/인쇄, Windows PowerPoint, 폰트 Gate 필요
- `INSTRUCTOR_PILOT → FIELD_PILOT`: 비저자 강사 리허설까지 필요
- `FIELD_PILOT → FIELD_READY`: 학생 파일럿까지 필요하고 품질·권리·SSOT Gate를 함께 통과해야 함
- `FIELD_READY → CANONICAL`: 위 조건에 더해 `releaseDecision: APPROVED` 필요
