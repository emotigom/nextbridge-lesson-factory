# R2 Release Contract

## immutable key

모든 승인 바이너리는 다음 키만 허용한다.

`courses/{courseId}/{version}/{sha256}/{filename}`

같은 key에 다른 bytes를 덮어쓰지 않는다. candidate/private evidence bucket과 public release bucket은 **별도 bucket**이어야 하며 prefix 이름으로 접근통제를 흉내 내지 않는다.

## promotion 순서

1. Full QA PASS
2. 사람 Gate + 품질 기준 + rights + reviewer + SSOT 확인
3. `RELEASE_APPROVED` 확인
4. SHA key로 각 asset 업로드
5. 동일 object를 다시 다운로드
6. size/SHA를 manifest와 재대조
7. 모든 exact SHA가 검증된 뒤에만 `courses/{courseId}/latest.json` 갱신

PR, `HOLD`, stale manual evidence, 품질/파일럿 지표 미달 상태는 3단계 전에 실패한다. `latest.json`은 바이너리 검증보다 먼저 바꾸지 않는다.

## 구현 명령

`tools/package/r2_publish.py`는 기본이 dry-run이다. 실제 쓰기는 `--execute`, `RELEASE_APPROVED=1`, production Environment 승인, R2 bucket/account/token이 모두 있어야 한다. 스크립트는 bucket·DNS·도메인·결제 설정을 생성하지 않는다.

```bash
python3 tools/package/r2_publish.py \
  --manifest releases/manifests/approved.json \
  --root candidate-output
```

실제 쓰기 경로는 승인 후에만:

```bash
RELEASE_APPROVED=1 \
R2_RELEASE_BUCKET=... \
CLOUDFLARE_ACCOUNT_ID=... \
CLOUDFLARE_API_TOKEN=... \
python3 tools/package/r2_publish.py \
  --manifest releases/manifests/approved.json \
  --root candidate-output \
  --bucket "$R2_RELEASE_BUCKET" \
  --execute
```
