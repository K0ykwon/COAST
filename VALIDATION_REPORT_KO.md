# COAST 실제 회로 검증 요약

상태: 로컬 구현 및 이상적 시뮬레이션 검증 완료. QPU 미실행.

- 실제 전체 후반 국면 회로: 13큐비트. 보정 회로: 14큐비트.
- 네 단계 QPY, native raw, 층별 모듈 등 독립 재로딩 검사 파일 17개 통과.
- 별도 실험 회로 11개 재로딩 통과.
- 표본 보정 final QPY 재로딩 통과.
- 원시 보드 집합·진폭, move 복원, 역연산, 임의 중첩 비교 통과.
- 최종 이상적 승리 표시 확률 ≈1. 최적 첫 수 선택확률 ≈0.4.
- 원시 최적화 회로: 23,980 CX, 2Q 깊이 20,136, all-to-all.
- 10개 작업 비트의 별도 23큐비트 원시 회로: 3,300 CX, 2Q 깊이 3,247; 재로딩·임의 입력·작업 비트 복원 검증 완료.
- 최종 독립 게이트 분해 기준: 4,186,152 CX. 실제 장비 비용은 미측정.
- 고정점 K=19는 B/B† 호출 수. 전체 final은 171회.
- 65,536개 모의 보정 샷의 q̂F=0.976806640625; 보정 final의 이상적 성공확률 0.9999999985367687.

검증 JSON: `results/actual_endgame_validation.json`, `actual_qpy_independent_reload.json`, `actual_experiment_validation.json`, `actual_shot_summary.json`, `actual_decoder_validation.json`.

정밀도 검증은 부동소수점 수치 검사다. 임의 입력 표본 검사는 전체 유니터리의 형식 증명이 아니다. 빈 49칸 전체 보드 구현과 실제 하드웨어 성공은 검증 범위에 포함하지 않는다.
