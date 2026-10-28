# COAST: 7×7 후반 국면 실험 계획 및 구현 검증

작성일: 2026-09-26. 대상: 빈칸 4개인 고정 오목 국면의 남은 모든 수. 규칙: 5개 이상 연속이면 승리하는 freestyle Gomoku, 금수 없음.

## 1. 완료 범위와 핵심 결론

**실제 상태 전파부터 최종 증폭까지 13큐비트로 구현했고, QPY 파일을 저장한 뒤 다시 읽어 검증했다. 1개 보조 큐비트를 사용하는 보정 회로는 14큐비트다.** 두 회로 모두 127큐비트 제한 안에 들어간다. 여기서 큐비트는 오류정정되지 않은 회로 선을 뜻한다.

고정된 45개 돌은 고전 상수로 사용한다. 남은 4칸은 실제 두 색 보드 레지스터로 표현한다. 종료 보드 ID나 종료상태표 StatePreparation을 이용하지 않는다. Uselect, Uwrite, Upred†, 종료 보정, 행동별 FPAA, 필터와 최종 회전이 모두 실제 게이트로 구현되어 있다. 미종료 잎을 깊이 제한으로 버리지 않는다.

컴파일러는 3⁴=81개 **국소 보드 입력의 판정 함수**를 전개한다. 일반적인 빈칸 수 E에서는 이 전처리가 지수적으로 커지므로, 빈 49칸 보드의 확장 가능한 구현이나 양자 우위를 입증한 결과는 아니다. 독립 DFS 종료상태 열거는 검증 정답에만 사용한다.

**QPU 실행은 하지 않았다.** 아래의 정확도, 샷 결과는 이상적 시뮬레이터 결과다. 하드웨어 backend와 연결을 지정한 배치·라우팅은 아직 수행하지 않았다. 큐비트 수는 충분하지만, 전체 최종 회로의 분해 비용은 수백만 CX 규모여서 장비 실행의 병목은 깊이와 오류다.

## 2. 고정 입력과 출력 의미

X=흑돌(1), O=백돌(2), ·=빈칸. 현재 둘 차례는 백돌 O다.

| 행 | 1열 | 2열 | 3열 | 4열 | 5열 | 6열 | 7열 |
|---|---|---|---|---|---|---|---|
| 1 | X | X | X | O | X | X | O |
| 2 | · | · | X | O | O | X | X |
| 3 | O | O | O | · | X | X | X |
| 4 | O | X | X | X | O | O | X |
| 5 | O | O | X | X | O | · | X |
| 6 | O | O | X | X | O | O | O |
| 7 | X | O | X | O | O | X | O |

| 행동 코드 a | 실제 위치(1부터) | 0부터 보드 인덱스 | 서로 다른 첫 종료 보드 수 Nₐ | 백 승리 비율 gₐ | minimax 값 |
|---:|---|---:|---:|---:|---:|
| 0 | 2행 1열 | 7 | 1 | 1 | +1 |
| 1 | 2행 2열 | 8 | 4 | 1/2 | 0 |
| 2 | 3행 4열 | 17 | 4 | 1/2 | 0 |
| 3 | 5행 6열 | 33 | 4 | 1/2 | 0 |

행동 0은 즉시 승리한다. 따라서 이 국면은 알고리즘 전체 연결을 확인하는 작은 검증 사례이며, 어려운 문제에서의 계산 우위 실험은 아니다. 최종 출력 분포는 승리 종료 보드 비율에 비례한다. 승리 결과 표본 확률 100%는 최적 첫 수를 고를 확률 100%라는 뜻이 아니다. 이 사례의 최적 첫 수 선택확률은 약 40%다.

## 3. 레지스터 및 회로 순서

| 레지스터 | Qiskit 인덱스 | 크기 | 의미 |
|---|---|---:|---|
| a | q0, q1 | 2 | 첫 수 주소, little endian |
| B | q2…q9 | 8 | 빈칸 4개의 (흑, 백) 비트 |
| m | q10, q11 | 2 | 현재 착수 주소, 층 종료 때 0 복원 |
| f | q12 | 1 | 균일 종료상태 준비 성공 플래그 |
| h | q13, 보정 실험만 | 1 | controlled-Q Hadamard test |

각 칸의 물리 비트쌍 (흑,백)은 빈칸=(0,0), 흑=(1,0), 백=(0,1)이다. (1,1)은 무효다. 측정 문자열은 왼쪽이 높은 비트 번호다. `measure_all()`이 qᵢ를 고전 비트 i로 옮긴다는 약속으로 해독한다.

1. H(a0), H(a1)로 첫 수를 균등 중첩한다.
2. B: 첫 돌을 쓰고 즉시 종료하면 보정한다. 이후 남은 3개 층에서 합법 착수 선택 → 가역 착수 → 전치 경로 역선택 → 새 종료상태의 결합 보정을 수행한다.
3. A: B/B†와 작업공간 0 반사, f 위상으로 행동별 FPAA를 수행한다. 이때 0 반사에 a를 포함하지 않는다.
4. F: 백 승리 및 f=1인 상태를 π/2로 표시하고 A를 이용해 π/2 diffusion을 수행한다. 여기의 원점 반사는 a를 포함한다.
5. 최종 회전: F에 대해 승리 위상과 diffusion 위상을 보정하고 측정한다.

이미 종료된 보드는 f=0 실패 가지도 더 진행하지 않는다. 종료 보정은 두 번의 Ry를 곱셈처럼 해석하지 않고, 사인 진폭 γ/[βₖ√c(t)]를 갖는 **하나의 회전**으로 구현한다. 회로에는 측정·reset·postselection을 중간에 넣지 않는다.

## 4. 고정점 복잡도와 합성 개선

이 국면에서는 γ²=1/6이고 모든 첫 수 뒤에는 적어도 하나의 종료 보드가 있으므로, 종료 보드 개수를 입력받지 않고도 pLB=1/6을 쓸 수 있다. δ=0.001에 대해 Yoder–Low–Chuang 위상열은 K=19, 일반화 반복 9개다. K는 초기 B를 포함한 B/B† 호출 수이며 게이트 수가 아니다. 이미 저장된 f에 작용하는 위상 게이트는 A 안에서 9개다.

표준 하한 기반 FPAA의 반복 규모는 O(log(1/δ)/√pLB)다. 하한 개선은 불필요하게 보수적인 반복을 줄이지만, 오라클 비용이나 최악의 경우 복잡도를 제거하지는 않는다. 이전 빈 보드 분석의 K=33과 여기의 K=19는 **서로 다른 입력의 결과**다.

QPY는 호환성을 위해 controlled-Ry를 `Ry(θ/2), MCX, Ry(-θ/2), MCX`라는 표준 게이트로 저장한다. 합성 전에 이 정확한 항등식을 인식해 controlled-Ry 전용 합성으로 돌린다. 동일 원시 회로의 CX 수는 **91,948 → 23,980**, 2큐비트 깊이는 **75,513 → 20,136**으로 줄었다. 이는 이 구현의 게이트 합성 개선이며 새로운 점근 복잡도 정리는 아니다. `submit_runtime.py`도 이 복원을 적용한다.

| 단계 | 큐비트 | B/B† 호출 수 | 이상적 승리 표시 확률 | 독립 게이트 분해 CX 수 |
|---|---:|---:|---:|---:|
| 원시 전파 B | 13 | 1 | 0.291666666667 | 23,980 |
| 행동별 고정점 증폭 A | 13 | 19 | 0.624999729630 | 460,840 |
| π/2 필터 F | 13 | 57 | 0.976562584491 | 1,392,168 |
| 최종 분수 회전 | 13 | 171 | 1.000000000000 | 4,186,152 |

마지막 열은 각 게이트를 보조 큐비트 없이 분해한 비용의 합이다. 전체 최적화 또는 실제 장비 라우팅을 마친 수치가 아니며 하한도 아니다. 원시 B는 별도로 전체 rz/sx/x/cx 회로를 만들어 **깊이 51,537, 2큐비트 깊이 20,136**를 확인했다. 최종 회로의 4,186,152 CX 기준 비용에는 보정용 별도 실험이 포함되지 않는다.

**원시 준비 단축 결과:** 원시 B의 동일한 13개 데이터 큐비트에 계산·해제용 깨끗한 작업 큐비트 10개를 더한 별도 **23큐비트 회로**를 생성했다. 상대위상 Toffoli와 정확한 역연산을 결합해 전체 B를 all-to-all 기본 게이트로 합성한 결과 **3,300 CX, 2큐비트 깊이 3,247**였다. 기존 13큐비트 B 대비 CX 절감률은 **86.24%**다. QPY 재로딩 후 |0⟩와 임의 복소 중첩 입력의 13개 데이터 진폭을 별도 검증기로 대조했고 모든 추가 작업 비트의 0 복원을 검사했다. 관련 기록은 `RAW_PREPARATION_OPTIMIZATION_KO.md`와 `results/actual_clean_workspace_optimization.json`에 있다. 이 합성 변화는 최악 시간복잡도를 줄이는 정리가 아니며 원래 13큐비트 최종 QPY 전체를 새 23큐비트 B로 다시 합성·검증했다는 주장은 아니다.

도달 가능한 초기 작업공간에서 첫 층의 보드가 a로 결정된다는 사실을 쓰면, 짧은 `root_coherent_simplified.qpy`는 **32 CX, 2큐비트 깊이 32**가 된다. 네 가지 합법 첫 수 입력에서 원래 첫 층과 일치함을 검사했다. 이것은 장비의 첫 검증 대상으로 제공하는 부분 회로다.

## 5. 완료한 검증과 수치 결과

- 독립 DFS와 성공 부분의 종료 보드 지지집합이 일치한다: 총 13개의 (첫 수, 종료 보드) 쌍.
- 각 성공 보드의 원시 진폭은 γ/2로 같고 pₐ=γ²Nₐ가 맞는다.
- raw, FPAA, filter, final에서 불법 보드·잘못된 루트·미종료 보드·복원되지 않은 move의 확률은 수치 오차 수준이다.
- 각 회로 뒤에 역연산을 붙이면 |0⟩로 돌아간다.
- 네 단계 QPY를 다시 읽어 별도 NumPy 인터프리터와 Qiskit Aer 결과를 비교했다. 가장 큰 진폭 차이는 약 4.4×10⁻¹⁴다.
- 네 단계에 대해 임의 복소 중첩 입력도 비교했다. 이는 목표 초기 상태 하나만의 검사를 보완하며 전체 유니터리의 완전한 형식 검증은 아니다.
- 기본 게이트로 분해한 원시 QPY도 재로딩 및 임의 입력 검사를 통과했다. 모든 비어 있지 않은 층별 모듈도 재로딩 후 임의 입력으로 확인했다.
- 잘못된 보드, move 오염, 정상 표본이 섞인 인위적 counts로 디코더를 확인했다. 실제 회로의 보드 레지스터용 디코더는 `analyze_actual_counts.py`다.
- 짧은 초기 모듈, 층별 prefix, echo, 읽기 대조군, 14큐비트 보정 회로의 저장·재로딩 검사도 통과했다.

| 항목 | 이상적 결과 |
|---|---|
| 원시 행동별 f=1 확률 | (0.166666667, 0.666666667, 0.666666667, 0.666666667) |
| FPAA 행동별 최소 f=1 확률 | 0.999999003900451 |
| FPAA 행동 분포 | (0.25, 0.25, 0.25, 0.25) |
| 필터의 승리 표시 확률 | 0.976562584490601 |
| 최종 행동 분포 | (0.399999774597, 0.200000075134, 0.200000075134, 0.200000075134) |
| 최종 승리 표시 확률 | 0.999999999999993 |
| 표본 보정 후 최종 이상적 승리 확률 | 0.999999998536769 |

검증 환경: Python 3.12.14, Qiskit 2.5.2, Aer 0.17.2, NumPy 2.3.5, SciPy 1.17.0. 회로 파일은 기본 QPY 형식으로 생성했다. 재현 시 먼저 제공된 버전을 사용한다.

### 유한 샷과 위상 보정

별도의 무잡음 시뮬레이션에서 raw/FPAA/filter/final을 각각 8,192회 측정했다. 최종 행동 counts는 **(3270, 1680, 1655, 1587)**이고 무효 출력은 0개였다. 이 8,192회에서 승리 실패가 없었다고 해서 실패확률 10⁻⁶을 통계적으로 입증한 것은 아니다. 예를 들어 0실패의 단측 95% 상한은 약 3/N이다. 10⁻⁶ 보장은 이론과 상태벡터 검증에 해당한다.

`calibration_Q1.qpy`는 Q=-D_F(π)S_G(π)를 controlled-Q로 실행한다. 전역 부호 -1도 제어될 때 상대 위상으로 반영한다. 이상적인 ancilla=1 확률이 qF와 일치함을 확인했다. 65,536개의 독립 보정 샷에서 q̂F=0.976806640625, 95% Wilson 구간 [0.975626013, 0.977931375]를 얻었다.

q̂F≥1/4이면 한 번의 분수 회전에 대해 φ=β=acos(1-1/(2q̂F))를 사용한다. 보정 샷만으로 위상을 정해 별도 QPY를 생성했고, 그 QPY의 동작도 재로딩 검증했다. 이상적 2차원 모델에서 실제 qF에 대한 잔여 실패는 (1-qF)(1-qF/q̂F)²이다. 이 식의 신뢰구간 평가는 하드웨어 게이트 잡음을 포함하지 않는다.

## 6. QPU 실행 계획

다음은 **앞으로 실행할 계획**이다. backend 이름·물리 큐비트·실행 날짜·job ID가 없는 현재 결과를 QPU 실험으로 보고하지 않는다.

| 순서 | 회로/조건 | shots 및 batch | 최대 계획 shots |
|---|---|---|---:|
| 1 | root_coherent_simplified, readout_zero, readout_one | 각각 4,096 × 3 batch | 36,864 |
| 2 | prefix_ply_2, prefix_ply_3, raw, raw_echo | 각각 8,192 × 3 batch | 98,304 |
| 3 | FPAA, filter, 이상적 보정 final | 각각 8,192 × 3 batch | 73,728 |
| 4 | calibration_Q1 | 독립 65,536 shots | 65,536 |
| 5 | 측정값 보정 final | 새 production 데이터 8,192 × 3 batch | 24,576 |
| 합계 | 모든 깊이 관문을 통과했을 때 | 추가 대조군 제외 | **299,008** |

실제 장비 target으로 합성한 뒤 활성 물리 큐비트 ≤127, native 2Q 수·깊이, 배치 및 라우팅, 가능하면 실행 시간과 보정 시점 오류율을 기록한다. backend 전체 폭으로 padding된 수와 실제 사용한 물리 큐비트 수를 구분한다.

깊은 단계는 무조건 제출하지 않는다. 먼저 32-CX 부분 회로와 읽기 대조군으로 확인한다. 이후 층별 회로의 실제 native 비용, 신호의 유지 여부, 접근 가능한 실행 한도를 보고 다음 단계 진행을 정한다. 원시 B는 13큐비트 버전이 23,980 CX이고 23큐비트 작업 비트 버전이 3,300 CX이지만, 통상적인 잡음 장비에서 최종 회로의 정확도가 유지된다고 가정하지 않는다. 실제 장비 라우팅 후 두 버전을 비교하고, 진행을 중단한 경우 실패한 깊이 관문을 그대로 기록한다.

각 batch에서 조건 순서를 무작위화한다. 읽기 결과는 원시 counts와 원래 shots 수를 유지한다. postselection이나 읽기 오류 완화 결과는 별도 부차 분석으로 제시한다. f 실패, 무효 보드, 종료 집합 밖 출력, move 오염을 모두 보고한다. 무효 범주는 서로 겹칠 수 있다.

주 지표는 행동 분포, f 성공확률, 승리 표시 확률, minimax 최적 행동 확률, 이상적 분포와의 TV 거리다. 승리 표시 확률과 행동 0의 확률을 혼동하지 않는다. batch별 수치와 95% 이항 구간을 함께 보고한다. 새로운 backend 데이터를 보고 이상적인 최종 위상을 사후 선택하지 않는다. 보정 데이터와 production 데이터는 분리한다.

## 7. 실행 및 재현 명령

패키지를 풀고 `coast_revision` 디렉터리에서 실행한다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 실제 회로 생성, 1차 검증
python src/build_actual_endgame.py
python src/optimize_clean_workspace.py
python src/write_clean_workspace_report.py

# 회전 항등식 복원 후 합성 최적화, 전체 단계 비용 산정
python src/optimize_actual_synthesis.py

# 저장 파일 자체 검증: 이 명령은 회로를 다시 생성하지 않는다
python src/validate_actual_endgame.py

# 짧은 모듈과 14큐비트 보정 회로 생성·재로딩 검증
python src/build_actual_experiments.py

# 무잡음 샷 실험 및 측정값을 이용한 최종 위상 보정
python src/run_actual_simulation.py
python src/calibrate_actual_final.py results/actual_simulated_counts/calibration_Q1.json

# 실행 계획의 수치 재생성
python src/write_actual_report.py
```

제공된 최종 QPY를 바로 읽는 최소 예:

```python
from qiskit import qpy
from qiskit_aer import AerSimulator

with open('circuits/actual_endgame/COAST_G7_E4_final.qpy', 'rb') as f:
    qc = qpy.load(f)[0]
assert qc.num_qubits == 13
qc.measure_all()
counts = AerSimulator(method='statevector').run(
    qc, shots=8192, seed_simulator=20260926
).result().get_counts()
```

IBM Runtime은 선택 의존성이며 저장된 사용자 계정과 접근 가능한 backend가 필요하다. 토큰을 코드에 넣지 않는다.

```bash
pip install qiskit-ibm-runtime

# 먼저 실제 target으로 컴파일만 수행
python src/submit_runtime.py --backend YOUR_BACKEND --qpy circuits/actual_endgame/experiments/root_coherent_simplified.qpy

# 장비에서 실행할 때만 --execute를 붙인다
python src/submit_runtime.py --backend YOUR_BACKEND --qpy circuits/actual_endgame/experiments/root_coherent_simplified.qpy --shots 4096 --execute

# root/prefix/echo는 해당 이상적 QPY와 전체 비트열을 비교
python src/analyze_actual_counts.py results/YOUR_ROOT_RESULT.json --reference-qpy circuits/actual_endgame/experiments/root_coherent_simplified.qpy

# 실제 raw/FPAA/filter/final의 결과 해독 예
python src/analyze_actual_counts.py results/YOUR_RUNTIME_RESULT.json

# 23큐비트 원시 B에서 10개 작업 비트의 오염까지 검사
python src/analyze_actual_counts.py results/YOUR_CLEAN_RAW_RESULT.json --clean-work 10

# 보정 회로 데이터는 별도의 비트 13을 읽는다
python src/analyze_actual_counts.py results/YOUR_CALIBRATION_RESULT.json --calibration
python src/calibrate_actual_final.py results/YOUR_CALIBRATION_RESULT.json --output circuits/actual_endgame/final_from_qpu_calibration.qpy
```

마지막 Runtime 명령의 파일명은 사용자가 받은 결과로 바꾼다. 제공한 decoder의 종료상태 검사는 raw 이후의 완전 전파 회로용이다. root/prefix/readout/echo 부분 회로는 해당 준비 목적에 맞는 이상적 분포 또는 레지스터 복원을 비교해야 하며, 미완성 보드를 종료 실패로 잘못 해석하지 않는다. Runtime 온라인 제출 경로는 계정 연결이 없어 실제 호출하지 않았다.

## 8. 파일 안내와 논문 반영

- `src/build_actual_endgame.py`: 실제 전파 회로 및 독립 NumPy 검증기.
- `src/optimize_clean_workspace.py`: 동일한 원시 준비의 23큐비트 작업 공간 재사용 합성, QPY 재로딩·임의 중첩 입력 검증.
- `src/optimize_actual_synthesis.py`: controlled-Ry 항등식 복원과 합성 자원 산정.
- `src/build_actual_experiments.py`: 부분 회로, echo, 읽기 대조군, 보정 회로.
- `src/calibrate_actual_final.py`: 실제/모의 보정 counts → 위상 → 새 final QPY.
- `src/validate_actual_endgame.py`: 저장 파일 직접 재로딩 검증.
- `src/analyze_actual_counts.py`: 보드 레지스터 기반 counts 해독 및 Wilson 구간.
- `circuits/actual_endgame/`: 실제 회로. `final`은 이상적 qF 보정 대조군이고 `final_shot_calibrated`는 제공된 모의 보정 샷을 사용한다.
- `results/actual_*.json`: 수치 검증, 합성 자원, 샷 결과 및 디코더 검사.
- `manuscript/main.pdf`: 실제 13/14큐비트 구현과 검증 결과를 반영한 7쪽 개정 논문.
- `EXPERIMENT_PROTOCOL_PREVIOUS_KO.md`: 앞선 전체 크기 모듈 및 대조군 계획의 기록.

앞선 4/6큐비트 표 기반 대조군, 105/110큐비트 승리 판정 모듈과 빈 보드 K=33 분석은 함께 보존했다. 이 자료와 현재의 실제 13큐비트 전파 회로를 구분한다. 빈 보드 49수 전체를 127큐비트 안에서 실행했다는 주장은 하지 않는다.

참고: Yoder, Low & Chuang, [Fixed-point quantum search with an optimal number of queries](https://arxiv.org/abs/1409.3305); IBM [QPY documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qpy). 구현·수치의 직접 근거는 동봉한 소스와 검증 JSON이다.
