# COAST: Reproducibility Materials

Code, circuits, and recorded results for **COAST: Coherent Outcome Aggregation over State Transpositions with Calibrated Amplification**, by Youngkwon Ko.

## Contents

- `src/`: classical analysis, circuit construction, synthesis and validation scripts.
- `results/`: recorded numerical results, input fixtures, synthesis metrics and simulated shot counts.
- `COAST_circuits.zip`: fixed-point controls, winner modules, reference circuits and four-empty-cell Gomoku propagation and calibration circuits (QPY). Extract it at the repository root to create `circuits/`.
- `requirements.txt`: recorded software versions.
- Korean experiment protocol and validation reports are included for reference.
- `ORIGINAL_PACKAGE_README.md`: original experimental instructions and additional context; references to the historical manuscript refer to the original supplied package.

## Reproduction

Use Python 3.12 and install the recorded dependencies:

```bash
python -m pip install -r requirements.txt
python -m zipfile -e COAST_circuits.zip .
python src/coast_analysis.py
python src/validate_actual_endgame.py
```

These commands may be computationally demanding. Circuit-generation and further reproduction commands are listed in `ORIGINAL_PACKAGE_README.md`. `src/make_tables.py` writes tables into `manuscript/`.

## Experimental scope

The recorded circuit executions are noiseless simulations. The full-board winner modules, classically table-prepared reference circuits, and the four-empty-cell reversible propagation circuit are separate artifacts. The 23-qubit clean-work optimization reported in the manuscript applies to raw state preparation.

The repository contains the materials supporting the manuscript; it does not include the separately developed post-manuscript 25-qubit full-final optimization.
