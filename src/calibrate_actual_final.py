"""Generate a final circuit from observed F-good or calibration_Q1 counts.

The supplied demo input is explicitly simulated data. No truth probability is
used to choose the angle. Formula applies to the one-fractional-step q>=1/4 case.
"""
import argparse,json,math,hashlib
from pathlib import Path
from qiskit import qpy
from build_actual_endgame import *
from analyze_actual_counts import summarize,wilson

def main():
    p=argparse.ArgumentParser();p.add_argument('counts',type=Path)
    p.add_argument('--from-filter',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args();payload=json.loads(a.counts.read_text());counts=payload.get('counts',payload)
    if a.from_filter:
        s=summarize(counts);qhat=s['marked_probability'];ci=s['marked_interval_95']
    else:
        n=sum(counts.values());k=0
        for key,c in counts.items():
            z=key.replace(' ','');idx=int(z,16) if z.startswith('0x') else int(z,2)
            if idx>=2**14:raise ValueError('Calibration counts must have at most 14 bits')
            k+=c*((idx>>13)&1)
        if not n:raise ValueError('Empty counts')
        qhat=k/n;ci=wilson(k,n)
    if qhat<.25:raise ValueError('Observed q<1/4: this one-step calibration is not applicable')
    phi=math.acos(1-1/(2*qhat))
    stages,_,_=build_stages();fops=stages['filter']
    ops=fops+mark(phi)+inv(fops)+zero_phase(tuple(range(N)),phi)+fops
    qc=circuit(ops,'COAST_G7_E4_final_measured_calibration')
    qc.metadata.update(calibration_probability=qhat,calibration_input_source=payload.get('source','user-provided counts'))
    path=a.output or OUT/'COAST_G7_E4_final_shot_calibrated.qpy'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb') as f:qpy.dump(qc,f)
    with path.open('rb') as f:loaded=qpy.load(f)[0]
    v=aer_state(loaded);err=aligned_error(simulate(ops),v);assert err<2e-9
    candidates=[*ci,qhat,(qhat+2)/3]
    worst=max((1-q)*(1-q/qhat)**2 for q in candidates if ci[0]<=q<=ci[1])
    report=dict(input_file=str(a.counts),input_source=payload.get('source','user-provided counts'),
        q_estimate=qhat,interval_95=ci,source_phase=phi,target_phase=phi,
        ideal_two_dimensional_failure_max_over_interval=worst,
        interval_interpretation='Statistical calibration uncertainty only; assumes ideal coherent F and reflections, excludes hardware gate noise',
        qpy_file=path.name,qpy_roundtrip_max_amplitude_error=err,
        ideal_simulated_marked_probability=float(np.sum(abs(v[good_mask()])**2)),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    path.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
