"""Reproducible NOISELESS sampled runs of the actual saved QPY circuits."""
import argparse,json
from qiskit import qpy
from qiskit_aer import AerSimulator
from build_actual_endgame import ROOT,OUT
from analyze_actual_counts import summarize,wilson

def main():
    p=argparse.ArgumentParser();p.add_argument('--shots',type=int,default=8192);a=p.parse_args()
    dest=ROOT/'results'/'actual_simulated_counts';dest.mkdir(exist_ok=True)
    sim=AerSimulator(method='statevector',max_parallel_threads=2)
    reports=[]
    for i,name in enumerate(('raw','fpaa','filter','final','calibration_Q1')):
        path=OUT/'experiments'/'calibration_Q1.qpy' if name=='calibration_Q1' else OUT/f'COAST_G7_E4_{name}.qpy'
        with path.open('rb') as f:qc=qpy.load(f)[0]
        qc.measure_all();shots=65536 if name=='calibration_Q1' else a.shots
        counts=sim.run(qc,shots=shots,seed_simulator=20260926+i).result().get_counts()
        payload={'source':'Qiskit Aer noiseless simulation; NOT QPU counts','stage':name,
                 'seed':20260926+i,'shots':shots,'counts':counts}
        (dest/f'{name}.json').write_text(json.dumps(payload,indent=2)+'\n')
        if name=='calibration_Q1':
            k=sum(v for key,v in counts.items() if (int(key,2)>>13)&1)
            summary=dict(q_filtered_estimate=k/shots,interval_95=wilson(k,shots))
        else:summary=summarize(counts)
        reports.append({'stage':name,**summary});print(name,summary,flush=True)
    (ROOT/'results/actual_shot_summary.json').write_text(json.dumps({'simulator_only':True,'runs':reports},indent=2)+'\n')

if __name__=='__main__':main()
