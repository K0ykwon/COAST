# COAST revision and experiment package

Read `EXPERIMENT_PROTOCOL_KO.md` for the current Korean execution plan and `VALIDATION_REPORT_KO.md` for the results. The September 26 revision implements the entire four-empty-cell endgame using 13 circuit qubits, with a 14-qubit calibration circuit. The empty 49-cell problem is not fully compiled, and no QPU was run.

## Actual propagation (new)

Unlike the terminal-table references below, `circuits/actual_endgame/` contains actual move selection, reversible writing, predecessor unselection, combined terminal attenuation, action-sector fixed-point amplification, filtering, and final amplification. The compiler expands local predicates over 3^4 inputs; this is not a polynomial compiler for arbitrary empty-cell counts. The four remaining plies are complete.

```bash
pip install -r requirements.txt
python src/build_actual_endgame.py
python src/optimize_actual_synthesis.py
python src/validate_actual_endgame.py
python src/build_actual_experiments.py
python src/run_actual_simulation.py
python src/calibrate_actual_final.py results/actual_simulated_counts/calibration_Q1.json
python src/write_actual_report.py
```

To verify the delivered circuits without regenerating them, run only `python src/validate_actual_endgame.py`. Reports are in `results/actual_*.json`. The sampled data are explicitly noiseless simulator data. `analyze_actual_counts.py` decodes the actual board registers; the older `analyze_counts.py` applies only to table-ID references.

`COAST_G7_E4_final.qpy` is the complete 13-qubit production circuit with ideal reference calibration. `COAST_G7_E4_final_shot_calibrated.qpy` instead uses separate simulated calibration shots. Both are real QPY files with built-in gates and no placeholder or opaque oracle. Portable controlled rotations are restored to dedicated controlled-Ry synthesis by `optimize_actual_synthesis.py` and by the Runtime submission script. The independent full-final CX expansion cost is 4,186,152 before cross-gate optimization or routing; width alone does not make this a practical noisy-device experiment.

**Shorter raw preparation:** `python src/optimize_clean_workspace.py` builds and reloads `actual_endgame/COAST_G7_E4_raw_clean23.qpy` and its native-basis version. Ten clean reusable work bits (23 total) and relative-phase compute/uncompute reduce the same raw preparation from 23,980 to **3,300 all-to-all CX** and from 20,136 to **3,247 two-qubit depth**. Both an all-zero and a fully coherent random data input were checked, as were the restored work bits and native QPY output. See `RAW_PREPARATION_OPTIMIZATION_KO.md`. The 13-qubit final QPY is the previously verified original version; a routed 25-qubit final circuit using this alternative B has not been synthesized or characterized.

Start prospective hardware tests with `experiments/root_coherent_simplified.qpy` (32 all-to-all CX). This is only a reachable-input-specialized root-layer test, not the full algorithm. Use actual backend compilation and independent hardware error assessment before advancing to deeper circuits.

## Contents

- `manuscript/main.pdf`: revised English manuscript (seven pages), including actual endgame implementation.
- `manuscript/*.tex`: complete LaTeX source and tables generated from JSON.
- `src/coast_analysis.py`: exact Tic-Tac-Toe recomputation, exact discrete candidate-board sampling, simultaneous confidence bound, YLC phase schedule and matrix checks.
- `src/build_circuits.py`: implemented winner modules and explicitly table-prepared reference circuits; ideal statevector checks and basis synthesis.
- `src/build_fpaa_controls.py`: six one-qubit fixed-point response controls, with barriers to preserve sequence boundaries; these do not prepare game states.
- `src/submit_runtime.py`: optional device compilation and explicitly enabled IBM Runtime submission.
- `src/analyze_counts.py`: raw-count decoding with an invalid-output bin and binomial intervals.
- `src/validate_exports.py`: saved-and-reloaded QPY validation, including QPE phase signs and probability distributions.
- `results/*.json`: software results, phase angles, board fixtures, environments and synthesis counts.
- `circuits/*.qpy`: earlier genuine winner and table-reference circuits, flattened to rz/sx/x/cx where applicable; `*_basis.qpy` is an explicit duplicate where supplied. One-qubit controls retain ordinary rotations and barriers. The new `actual_endgame/` subdirectory uses portable built-in multi-controlled gates; `raw_native` is separately decomposed. None is a device-native routed circuit.

## Reproduce

```bash
pip install -r requirements.txt
python src/coast_analysis.py
python src/build_circuits.py
python src/build_fpaa_controls.py
python src/validate_exports.py
python src/make_tables.py
cd manuscript
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

No hardware execution has been performed. The full empty-board 49-ply preparation is not implemented. Actual endgame propagation and table-prepared references coexist and are labeled separately. These boundaries must be retained when reporting results.

`submit_runtime.py` requires a user-saved IBM account and an accessible backend. It compiles only unless `--execute` is supplied. The online submission path was not tested with a live account. Qiskit Runtime is an optional, separate installation.

## Important numeric interpretation

The final discrete sampler's common lower bound is 0.05582790630199844. With amplitude error 0.001, the YLC schedule has K=33 raw preparation/inverse calls, not 33 device gates. The bound is statistical at family confidence 99% and relies on the ideal preparation identity. The winner module is 110 circuit qubits; retaining root/move/success/iterative-phase wires makes the winner stage 124 wires. Neither value certifies the width or runtime of the complete algorithm.
