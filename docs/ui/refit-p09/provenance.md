# P09 v2 기준 P06 화면 캡처 출처

- 실제 화면: P06 `static/index.html`, `static/styles.css`, `static/app.js`를 loopback 서버와 설치된 Chrome headless로 열어 캡처했습니다. `scripts/capture_refit.py`가 포트 19106/19107을 사용하고 종료 시 두 프로세스를 정리합니다.
- 브라우저 상태: `model_enabled=false`. 실제 API의 카탈로그 GET, source 질의 POST, 저장 기록 GET, 정책 보류 RAG/All-context 요청, 모델 비활성 RAG/All-context 요청만 사용했습니다. **모델 추론 0회**입니다. 정책 보류는 서버가 모델을 부르기 전에 반환한 실제 결과입니다.
- CPU 브라우저 검사: `browser-check.json`의 17개 기본 흐름과 `policy-check.json`의 5개 보류/모바일 검사 통과. 검사 과정에 지연 전송·미존재 기록·인용 렌더러를 검증하는 명시적 mock이 있으나 **아래 10개 PNG에는 그 mock 상태를 사용하지 않았습니다.** `07-model-disabled-comparison.png`는 실제 비활성 서버 응답입니다.
- 화면 제한: 이 캡처는 개발용 공개 카탈로그 스냅샷 8행 또는 50행만 다룹니다. 원문 문서 ID는 물리 장비 식별자가 아닙니다. 원문 인용의 정확한 문자열 검사는 성능이나 방문 권한 검증이 아닙니다. 평가 파일은 읽지 않았고 12건 정식 결과를 주장하지 않습니다.
- 과거 UI의 실제 Qwen 개발 시연과 영상은 `../actual-model-d1/provenance.md`에 보존합니다. 새 화면을 위해 추론하거나 과거 캡처를 편집하지 않았습니다.

| 실제 Chrome 이미지 | SHA-256 |
|---|---|
| `01-source-desktop.png` | `b279fd56e7a99a942a9975177b3cd15aa26605ccd042cd12309e3a2e65810670` |
| `02-query-source.png` | `8bad7939e023ccc1547a5029a88a35bc556677fb75b7309973dada444365e1df` |
| `03-original-drawer.png` | `281916be2391e6dfa22d2ff7c056ced11a873df77e9f8becf1e1f0ce2f4d9a75` |
| `04-preview50-source.png` | `010805887df18965196b9a6ce80942e15055b5ea4fe2f5e54181ef77138644f5` |
| `05-mobile-query.png` | `47f0de94a6f61fc30b6d561d180faa2b130fadd1da772fad87edea4634ede85f` |
| `06-mobile-receipts.png` | `b881e8b2f3112cc466f9324b81d5a1a231d1bdbfdb8c409053c2a5addaeaf71b` |
| `07-model-disabled-comparison.png` | `02e8e27c512963384af72159f018d5a1d196223157a5ed39a8d9e37ae4b2ecbd` |
| `policy-live-state-desktop.png` | `092adb932194e95e0de85133f5773e5227d2ef2aabbf685e5e4bdff3a8a1c095` |
| `policy-physical-identity-desktop.png` | `d509355efb4597c81636c2151dae5e4369a0b14de0f4dc7fa61b4afbfdbc6215` |
| `policy-physical-identity-mobile.png` | `693cee9bde6ae7fc5e8f7ef74536f403c3145f2ba8e30db7f02edc445eedb28c` |

브라우저 보고서 SHA-256: `browser-check.json` `cf2b3f8896f031bfd3981ccbdcb97d43451559a482a762e70ce15db1037eede0`, `policy-check.json` `511f0744f67169d2c322ef587b65ca7a2076be2f2d745e2d4bea8a844f744c12`.
