import json
from pathlib import Path
from coast_analysis import ROOT

c=json.loads((ROOT/'results/gomoku_calibration.json').read_text())
t=json.loads((ROOT/'results/ttt_exact.json').read_text())
r=json.loads((ROOT/'results/circuit_resources.json').read_text())
out=ROOT/'manuscript'
(out/'numbers.tex').write_text(r'\newcommand{\CalibrationLower}{'+f"{c['common_lower']:.7f}"+'}\n')
rows=[]
for row in c['rows']:
    a,b=row['root'];rows.append(f"({a},{b}) & {row['hits']:,} & {row['p_est']:.5f} & {row['p_lower']:.5f} \\")
rows=[row+'\\' for row in rows]
(out/'calibration_table.tex').write_text('''\\begin{table}[t]
\\centering\\small
\\caption{Gomoku preparation calibration; 20,000 samples per root class. Coordinates are zero-based. Bounds are simultaneous at family confidence 99\\%.}
\\label{tab:cal}
\\begin{tabular}{crrr}\\toprule
Root & Accepted & $\\widehat p_a$ & Lower bound\\\\\\midrule
'''+ '\n'.join(rows)+'''
\\bottomrule\\end{tabular}
\\end{table}
''')
labels=[('Uniform optimal-action probability','uniform_optimal_probability'),('Filtered optimal-action probability','filtered_optimal_probability'),('Exact-final optimal-action probability','exact_final_optimal_probability'),('Exact-final marked-outcome probability','exact_final_marked_probability'),('Agreement: smallest-index tie','smallest_index_tie_agreement'),('Agreement: uniform tie','uniform_tie_agreement'),('Agreement: all maximizers optimal','all_maximizers_optimal_agreement')]
rows=[f"{label} & {100*t['metrics'][key]:.4f} \\\\" for label,key in labels]
(out/'ttt_table.tex').write_text('''\\begin{table}[t]
\\centering\\small
\\caption{Recomputed ideal Tic-Tac-Toe metrics over all 4,520 nonterminal states (percent). Final calibration is exact.}
\\label{tab:ttt}
\\begin{tabular}{lr}\\toprule Metric & Value\\\\\\midrule
'''+ '\n'.join(rows)+'''
\\bottomrule\\end{tabular}\\end{table}
''')
entries=[('Winner, compact',r['modules']['winner7']),('Winner, reusable work',r['modules']['winner7_fast']),('TTT filter',r['references']['ttt_late']['filter']),('TTT final',r['references']['ttt_late']['final']),('Gomoku endgame filter',r['references']['gomoku_four_empty']['filter']),('Gomoku endgame final',r['references']['gomoku_four_empty']['final'])]
entries.extend([('TTT QPE (4 phase bits)',r['references']['ttt_late']['qpe4']),('Gomoku QPE (4 phase bits)',r['references']['gomoku_four_empty']['qpe4'])])
rows=[]
for label,x in entries:
    b=x['basis_all_to_all'];rows.append(f"{label} & {x['qubits']} & {b['cx']:,} & {b['two_qubit_depth']:,} \\\\")
(out/'resource_table.tex').write_text('''\\begin{table}[t]
\\centering\\scriptsize
\\caption{Executed all-to-all basis synthesis. Two-qubit depth counts CX layers. No backend routing or hardware measurements are included.}
\\label{tab:resources}
\\begin{tabular}{lrrr}\\toprule Circuit & Qubits & CX & 2Q depth\\\\\\midrule
'''+ '\n'.join(rows)+'''
\\bottomrule\\end{tabular}\\end{table}
''')
print('Generated manuscript tables from recorded JSON results.')
