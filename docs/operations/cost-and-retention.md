# 비용·보존기간·예산 Hard Stop

정상 운영 목표는 **월 추가비용 $0**이다.

## 정책

- public repo의 standard GitHub-hosted runner만 허용한다.
- larger runner는 금지한다.
- PR QA artifact는 1일, 실패 증거는 최대 3일만 보존한다.
- 성공한 대형 렌더를 Actions artifact에 누적하지 않는다.
- Workers Static Assets는 정적 요청을 우선하고 `/api/*`만 Worker를 먼저 실행한다.
- R2는 Standard만 사용한다.
- Workers Paid, Containers, 유료 SaaS, larger runner는 `config/budget-policy.json`에서 false다.

## 사전 차단선

- R2 Standard storage 9 GB-month
- R2 Class A 800,000 / month
- R2 Class B 8,000,000 / month
- Worker dynamic request 80,000 / day

이 값은 무료 구간보다 낮게 잡은 **파이프라인 자체 soft limit + publish hard stop**이다. 제공자 계정의 절대 billing cap은 아니다.

## 유료 전환 절차

한도를 넘을 것으로 예측되면 배포를 중단하고 (1) 원인, (2) 예상 월 사용량, (3) 예상 월비용, (4) 무료 대안, (5) 품질 영향 을 보고한 뒤 명시적 승인을 받는다.

공식 기준 링크:
- GitHub Actions billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub artifact retention: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
- Cloudflare Workers pricing: https://developers.cloudflare.com/workers/platform/pricing/
- Workers Static Assets billing: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/
- R2 pricing: https://developers.cloudflare.com/r2/pricing/
