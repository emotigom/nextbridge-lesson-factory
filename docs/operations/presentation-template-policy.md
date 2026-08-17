# Presentation template policy

2026 찾아가는 AI교육 계열 교안은 지정 PPTX 템플릿을 먼저 확인한 뒤 PPTX 제작 Gate로 이동한다.

## Public Git 경계

지정 템플릿 PPTX 원본은 public Git에 저장하지 않는다. Public Factory에는 템플릿의 SHA-256, 구조 지문, 적용 범위, candidate PPTX가 가져야 할 custom properties만 기록한다.

현재 등록된 정책:

- `policies/presentation-templates/2026-visiting-ai.json`

## Course binding

해당 사업의 candidate course contract는 `presentationTemplate`을 명시한다.

```json
{
  "presentationTemplate": {
    "templateId": "2026-visiting-ai",
    "policyPath": "policies/presentation-templates/2026-visiting-ai.json"
  }
}
```

`presentationTemplate`이 있는 course를 private package replay로 검사할 때 Factory는 PPTX 구조 검사 뒤에 presentation-template Hard Gate를 자동 실행한다.

## Candidate PPTX Hard Gate

해당 범위의 PPTX candidate는 다음 custom properties를 포함해야 한다.

- `NextbridgeTemplateId`
- `NextbridgeTemplateSha256`
- `NextbridgeTemplateScope`
- `NextbridgeTemplatePolicy`

그리고 등록된 policy의 구조 지문과 일치해야 한다.

- slide size
- slide master 수
- slide layout 수와 이름
- 모든 slide → layout binding
- 모든 layout → master binding
- 표지 필수 문구
- 종료 슬라이드 필수 문구

하나라도 다르면 `presentation_template_hard_gate`는 FAIL이다.

패키징 전에 PPTX만 빠르게 확인할 수도 있다.

```bash
python3 tools/lessonctl/presentation_template.py \
  --pptx /secure/candidate.pptx \
  --template-id 2026-visiting-ai
```

검사 구현:

- `tools/lessonctl/presentation_template.py`
- `tools/lessonctl/private_replay.py`
- `tests/test_presentation_template.py`

템플릿을 나중에 적용하면 PPTX SHA와 실행패키지 SHA가 바뀐다. 따라서 Windows PowerPoint, 폰트 이식성, 독립 강사 리허설, 학생 파일럿 등 이미 수집된 수동 Gate evidence는 새 SHA 기준으로 다시 보아야 한다.

## 권리 경계

템플릿 원본, 기관 비주얼, 로고, 배경 일러스트는 별도 권리 검토 전까지 public distribution을 승인하지 않는다. `rights.status`와 `publicDistributionApproved`는 사람이 검토한 뒤에만 변경한다.
