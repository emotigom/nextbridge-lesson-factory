# ChatGPT → Nextbridge Factory handoff 요청 템플릿

교안 설계 대화에서 승인된 내용을 Factory로 넘길 때 사용합니다.

아래 블록을 **현재 교안 제작 ChatGPT 대화방**에 붙여넣습니다.

```text
지금까지 이 대화에서 제가 명시적으로 승인한 내용만 사용해서
Nextbridge Lesson Factory용 `handoff.json`을 만들어주세요.

중요 규칙:

1. 승인되지 않은 초안이나 폐기된 문구를 되살리지 마세요.
2. 다른 채팅, 과거 PPTX/HTML/PDF, 기억 속 이전 교안 내용을 보충하지 마세요.
3. 현재 대화에서 허용된 자료만 `sourcePolicy.allowedInputs`에 기록하세요.
4. clean-room 입력 범위를 제가 승인한 경우 `approvals.cleanIntake`에 승인자와 승인 시각을 기록하세요. 승인되지 않았다면 handoff를 다음 단계로 올리지 마세요.
5. 학생 화면 문장과 교사용 대본을 섞지 마세요.
6. 각 차시 storyboard는 실제 승인된 상태인 경우에만 `APPROVED`로 넣으세요.
7. 승인되지 않은 차시는 storyboard 배열에 넣지 말고 approval을 `PENDING`으로 두세요.
8. `designState`는 임의로 높이지 말고 현재 승인 상태와 정확히 맞추세요.
9. `ALL_CONTENT_APPROVED`일 때만 `qualityScore`를 포함하세요.
10. ChatGPT 대화 전문이나 개인 정보는 handoff에 넣지 마세요.
11. `privateConversationEvidence.detailPublished`는 반드시 false로 두세요.
12. `approvals.cleanIntake`, `approvals.courseMap`, 각 차시 approval, `approvals.allContent`에는 실제 승인된 경우에만 reviewer와 approvedAt을 기록하세요.
13. 출력은 설명문 없이 유효한 JSON 하나만 제공하세요.
14. 스키마는 Nextbridge Factory의 `contracts/chatgpt-handoff.schema.json` 1.0.0을 따르세요.
```

## 권장 저장 위치

실제 handoff에는 학생 화면·교사 대본 등 상세 교안이 들어갈 수 있으므로 public Git에 커밋하지 않습니다.

예:

```text
/private-work/feed-why/handoff.json
```

## 검증

```bash
python3 tools/lessonctl/handoff.py validate \
  --file /private-work/feed-why/handoff.json
```

전체 상세 설계가 승인된 뒤에만 Factory design bundle로 변환합니다.

```bash
python3 tools/lessonctl/handoff.py materialize \
  --file /private-work/feed-why/handoff.json \
  --out /private-work/feed-why/design-bundle
```

`materialize`는 `ALL_CONTENT_APPROVED`가 아니면 실패합니다. 생성된 bundle은 기존 `content_design.py` 검사를 다시 통과해야 합니다.
