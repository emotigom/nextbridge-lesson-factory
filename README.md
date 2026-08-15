# Nextbridge Lesson Factory

교안을 많이 만드는 저장소가 아니라, **한 번에 하나(WIP=1)**의 교안을 검증 가능한 상태로 만들고 Gate를 통과한 결과만 배포하기 위한 파이프라인입니다.

## 비협상 원칙

- `DRAFT → CONTENT_QA → TECH_QA → INSTRUCTOR_PILOT → FIELD_PILOT → FIELD_READY → CANONICAL`
- 현재 활성 교안이 `FIELD_READY` 이상이 되기 전에는 다음 교안을 시작하지 않습니다.
- 원본 학교자료·개인정보·권리 불명 자산·실제 배포용 대형 바이너리는 public Git에 넣지 않습니다.
- 자동 QA는 파일을 몰래 고치지 않습니다. Hard Gate 실패는 non-zero exit로 중단합니다.
- `INTEGRITY_PASS`와 `RELEASE_APPROVED`는 다른 상태입니다.
- PR은 Fast QA, 승인 candidate/release는 Full QA입니다.
- Cloudflare Worker는 `/api/*`와 전달 계층에만 사용하며 LibreOffice/PowerPoint 렌더를 실행하지 않습니다.

## 빠른 실행

```bash
python3 tools/lessonctl/lessonctl.py intake courses/feed-why/course.yaml
python3 tools/lessonctl/lessonctl.py qa fast --course feed-why --json out/gate-report.json
python3 tools/lessonctl/lessonctl.py qa full --course feed-why --json out/gate-report-full.json
python3 -m unittest discover -s tests -v
python3 tools/lessonctl/lessonctl.py budget check
node --check worker/src/index.js
```

실제 v0.4 private 패키지를 로컬에서 재검증할 때만 다음처럼 경로를 넘깁니다.

```bash
python3 tools/lessonctl/lessonctl.py qa full \
  --course feed-why \
  --private-package /path/to/넥스트브릿지_내피드는왜이래_수직시제품_실행패키지_v0.4.zip \
  --json out/feed-why-full-private.json
```

## 공개/비공개 경계

현재 5장 수직시제품의 실제 ZIP/PPTX/HTML은 공개 저장소에 커밋하지 않습니다. 이 저장소에는 검증된 SHA, 기대 결과 계약, synthetic fixture만 둡니다. 자세한 결정은 `docs/decisions/0001-lesson-factory-architecture.md`를 참고하세요.

## R2 / Cloudflare 안전 경계

`tools/package/r2_publish.py`는 `HOLD`, FIELD_READY 미만, 품질/권리/SSOT/사람 Gate/파일럿 지표 미충족 release를 hard fail한다. 기본 실행은 dry-run이며 실제 R2 write는 production 승인과 명시적 `--execute` 없이는 수행하지 않는다. 현재 저장소 bootstrap PR에서는 Cloudflare production 배포나 R2 write를 실행하지 않는다.
