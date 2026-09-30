# 실제 모델 D1 UI 시연 출처

이 자료는 **개발용 UI 시연 한 건**입니다. CPU 모델 미사용 기준선과 구분하며, 동결 12개 질의 평가나 장비 적합성·의미 검증 결과가 아닙니다.

| 항목 | 실제 관측 |
| --- | --- |
| 질문 | N9030A에 적힌 최대 반송파 주파수는 얼마인가? |
| 방식·모델 | RAG · qwen3:4b |
| 원문 범위 | 2026-04-17 KERI 카탈로그의 고정 8행 중 검색된 3행 |
| 기록 ID | fc38c5e16dba14e9f84deb19 |
| 응답 상태 | model_validated_citations_only · SUPPORTED |
| 실제 모델 요청 | 1건, 재시도 없음 |
| 전체 wall time | 6.366초, 이 호출의 관측값 |
| 입력 토큰 | CPU 재구성 1254 = runner 1254 |
| 출력·종료 | 211토큰 · stop |
| 관측 thinking 문자 | 0, 일반적인 비활성화 보장으로 해석하지 않음 |
| trace ID | c4e08a62327545659d30c005b87d0153 |
| 의미 검증 | semantic_entailment_verified=false |

화면의 **N9030A의 최대 반송파 주파수는 44GHz입니다.**라는 제안은 자료 기록 `KERI-20260417-preview-44`의 구성 및 성능 필드 **Maximum 44GHz Carrier Frequency**와 일치했습니다. 서버가 검사한 원문 인용과 Unicode span을 실제 대화상자에서 강조하고, 돌아가기의 포커스 복귀와 390px 화면을 확인했습니다. 원문 전체는 [공공데이터포털 KERI 장비보유현황](https://www.data.go.kr/data/15018891/fileData.do)의 제한된 DOM 스냅샷이며, 현재 가용성·예약·접근권한의 증거가 아닙니다.

## 선별 공개 화면

- [실제 모델 질문 입력](actual-model-input-desktop.png)
- [실제 모델 데스크톱 응답](actual-model-outcome-desktop.png)
- [실제 원문 인용 강조](actual-model-quote-desktop.png)
- [실제 모델 390px 응답](actual-model-outcome-mobile.png)
- [실제 원문 인용 390px](actual-model-quote-mobile.png)
- [실제 작업 영상](video/workflow.mp4)

PNG는 원본 브라우저 viewport 캡처입니다. 원문·모델 결과·성공 문구를 합성하거나 수정하지 않았습니다. 실제 모델 시연은 이 한 건뿐이며, 다른 방식의 미실행 상태를 성공으로 표시하지 않았습니다.

영상은 원본 native Chrome screencast 프레임 8개와 관측 시간 간격으로 인코딩했습니다. 정적 화면을 다음 원본 프레임까지 유지하고, 마지막 원본 프레임을 유지용으로 반복해 MP4에는 9프레임이 있습니다. 출력은 H.264, 1440×1000, **12.04초**, **434598 bytes**이며 전체 디코딩 검사에 통과했습니다. 성공 오버레이나 가상 응답을 추가하지 않았습니다. SHA256은 `89edd0cb1cc2215a32dd1faf8bf49e5ad288c3e35cb57e7d12634080808d81aa`입니다.

원본 요청·응답 기록, 원본 프레임·타임스탬프, 인코딩 입력은 작업 원본에 보존하며 공개 export 대상에서는 제외합니다. 공개 자료는 선별 PNG 5장·영상·이 문서입니다. 캡처 후 공유 차단 표시가 없고 lease가 사용 가능한 상태를 확인했습니다. 화면에는 인증 정보·호스트·계정 경로가 없습니다.
