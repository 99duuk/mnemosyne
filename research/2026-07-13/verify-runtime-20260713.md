# Runtime Verification - 2026-07-13

## Naver policy surface

- `https://blog.naver.com/robots.txt` returned HTTP/2 200 at 2026-07-13 20:22 KST.
- Response `Last-Modified`: 2025-10-21 11:29:58 GMT.
- Body SHA-256: `b0a0a5a0aa415af00955e98be932403dc9d99fcb7626b45fcd169b97e1c113b4`.
- Body still contained the explicit AI training/RAG prohibition and named AI user-agent blocks.
- Temporary header/body files were deleted after verification.

This verifies the current public response, not a copyright license or the exact historical deployment date.

## Synthetic temporal/quote fixture

Input claims:

- `old`, valid 2021-01-01 through 2023-12-31: `나는 원격근무를 선호한다.`
- `new`, valid from 2024-01-01: `지금은 사무실에서 동료와 협업하는 방식을 더 선호한다.`

Observed Node result:

```json
{"historical":["old"],"current":["new"],"exact":true,"altered":false}
```

Assertions passed:

- `as_of=2022-06-01` selected only `old`.
- `as_of=2026-07-13` selected only `new`.
- One exact NFC source substring passed.
- An altered stronger quote failed.

This confirms only deterministic pre-ranking temporal eligibility and exact-substring mechanics on a synthetic authorized fixture. It does not validate dense retrieval, contradiction/NLI quality or persona fidelity.
