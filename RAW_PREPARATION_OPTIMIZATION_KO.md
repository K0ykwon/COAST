# COAST 원시 준비 회로 단축 결과

7×7 오목에서 빈칸이 4개인 앞서 검증한 국면의 **동일한 원시 준비 B**를 대상으로 한다. 종료상태표의 진폭 준비로 대체하지 않았다. 원래 13개 데이터 큐비트는 그대로 두고, 계산·해제에 재사용할 깨끗한 작업 큐비트 10개를 추가했다.

| 구현 | 폭 | all-to-all CX | 2큐비트 깊이 | 검증 상태 |
|---|---:|---:|---:|---|
| 기존 회전 전용 무보조 합성 | 13 | 23,980 | 20,136 | QPY 재로딩 및 상태벡터 검증 완료 |
| 정확한 Toffoli 작업 비트 | 23 | 9,640 | 8,025 | QPY 재로딩·임의 입력 검증 완료 |
| 상대위상 Toffoli 계산·해제 | 23 | **3,300** | **3,247** | QPY 재로딩·임의 입력·기본 게이트 검증 완료 |

이번 최종 방식의 무보조 기준 CX 절감률은 **86.24%**다. 하나의 2제어 계산 단계에서 보통 Toffoli의 CX 6개 대신 상대위상 Toffoli의 CX 3개를 사용한다. 계산 중 생긴 위상은 제어 비트와 계산된 작업 비트를 보존한 채 게이트를 적용한 뒤 정확한 역연산으로 해제되므로 소거된다. 타깃 데이터 비트를 뒤집는 최종 연산은 여전히 정확한 Toffoli를 사용한다. 이는 게이트 합성의 상수 인자 감소다.

이상적인 원시 B의 행동별 성공 플래그 확률은 (1/6, 2/3, 2/3, 2/3)으로 유지된다. 새 QPY를 디스크에서 다시 읽고 |0⟩ 입력 및 **임의 복소 중첩의 전체 13데이터 큐비트** 입력을 별도의 NumPy 원시 준비 인터프리터와 비교했다. 작업 비트로 유출된 확률은 각각 4.27e-28, 1.31e-27다. 기본 게이트 rz/sx/x/cx로 분해한 QPY에서도 진폭 최대 오차는 3.49e-14, 작업 비트 잔여 확률은 2.06e-29였다. 수치는 부동소수점 검증이다.

QPY 파일:

- `circuits/actual_endgame/COAST_G7_E4_raw_clean23.qpy`: 23큐비트 실행 가능한 표준 게이트 회로.
- `circuits/actual_endgame/COAST_G7_E4_raw_clean23_native.qpy`: 같은 회로를 all-to-all rz/sx/x/cx로 분해한 기준 회로. 실제 장비의 연결·ISA는 미반영.
- `results/actual_clean_workspace_optimization.json`: 폭, 게이트 수, 깊이, 오차, SHA-256.

패키지의 `coast_revision` 디렉터리에서 재생성:

```bash
python src/optimize_clean_workspace.py
python src/write_clean_workspace_report.py
```

QPU에 제출하기 전에는 사용자 계정과 실제 backend를 지정하여 먼저 target 합성만 실행한다.

```bash
python src/submit_runtime.py --backend YOUR_BACKEND --qpy circuits/actual_endgame/COAST_G7_E4_raw_clean23.qpy
```

실제 counts가 생기면 다음 명령으로 작업 비트 오염을 별도 보고한다.

```bash
python src/analyze_actual_counts.py results/YOUR_RUNTIME_RESULT.json --clean-work 10
```

**범위:** 이 절감은 이번 국면의 원시 준비 B에 대해 실측한 all-to-all 합성 값이다. 원래 13큐비트 `final.qpy`는 변경되지 않았으며, 새 23큐비트 B를 반복 호출하는 최종 25큐비트 회로의 native 총 비용이나 장비 성공확률을 여기서 측정한 것으로 해석할 수 없다. 장비 연결에 따른 SWAP이나 더 많은 활성 큐비트의 오류도 포함되지 않았다. 이 국소 보드 컴파일러는 빈칸 E에 대해 3^E개 배치를 열거하므로, 이번 최적화로 전체 49수의 시간복잡도가 깊이에만 선형이 되지는 않는다. 실제 QPU는 아직 실행하지 않았다.
