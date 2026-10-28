"""Small-input QPU controls and a one-ancilla amplitude calibration circuit.

Only local ideal simulation is run here. All QPY circuits are unmeasured;
submit_runtime.py adds qubit-order-preserving measurements at submission.
"""
import json,math,hashlib
from qiskit import qpy,transpile
from qiskit.transpiler.passes.synthesis import HLSConfig
from build_actual_endgame import *

def main():
    stages,modules,meta=build_stages();raw,_,bmeta=build_B()
    out=OUT/'experiments';out.mkdir(exist_ok=True)
    rows=[]
    experiments={}
    # Reachable-input specialization of the root layer: after Uwrite, the
    # board is a deterministic function of a, so attenuation needs a only.
    # It agrees with the full root module on all four legal root inputs.
    specialized=[Op('x',pattern(A,a),2+2*a+PLAYER-1) for a in range(4)]
    for a in range(4):
        b=tuple(PLAYER if i==a else 0 for i in range(4))
        if is_terminal(b):specialized.append(Op('ry',pattern(A,a),FLAG,2*math.asin(bmeta['gamma'])))
    for a in range(4):
        init=[Op('x',target=q) for j,q in enumerate(A) if (a>>j)&1]
        assert aligned_error(simulate(init+specialized),simulate(init+modules['root']))<1e-12
    experiments['root_coherent_simplified']=([Op('h',target=q) for q in A]+specialized,N)
    for a in range(4):
        init=[Op('x',target=q) for j,q in enumerate(A) if (a>>j)&1]
        experiments[f'root_action_{a}']=(init+modules['root'],N)
    for ply in (2,3):
        cut=bmeta['layers'][ply-1]['cumulative_ops']
        experiments[f'prefix_ply_{ply}']=([Op('h',target=q) for q in A]+raw[:cut],N)
    # Coherent echo retains the full input/output map, not a classical check.
    experiments['raw_echo']=([Op('h',target=q) for q in A]+raw+inv(raw),N)
    experiments['readout_zero']=([],N)
    experiments['readout_one']=([Op('x',target=q) for q in range(N)],N)
    # Q = -D_F(pi) S_good(pi); preserve its global minus under control.
    fops=stages['filter']
    qops=mark(math.pi)+inv(fops)+zero_phase(tuple(range(N)),math.pi)+fops+[Op('phase',angle=math.pi)]
    controlled=[Op(o.kind,o.cond+((N,1),),o.target,o.angle) for o in qops]
    experiments['calibration_Q1']=(fops+[Op('h',target=N)]+controlled+[Op('h',target=N)],N+1)
    for name,(ops,n) in experiments.items():
        qc=circuit(ops,name,n);path=out/f'{name}.qpy'
        if name=='calibration_Q1': qc.metadata['calibration_bit']=N
        with path.open('wb') as f:qpy.dump(qc,f)
        with path.open('rb') as f:loaded=qpy.load(f)[0]
        expected=simulate(ops,n=n);actual=aer_state(loaded)
        err=aligned_error(expected,actual);assert err<2e-9
        row=dict(name=name,file=str(path.relative_to(OUT)),qubits=n,
                 qpy_reload_max_amplitude_error=err,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if name=='calibration_Q1':
            p1=float(np.sum(abs(actual[2**N:])**2))
            assert abs(p1-meta['analytic_q_filtered'])<2e-9
            row.update(ancilla_one_probability=p1,expected_q_filtered=meta['analytic_q_filtered'])
        if name.startswith('root_'):
            from optimize_actual_synthesis import native_compile
            native=native_compile(loaded)
            row['native_all_to_all']=dict(cx=int(native.count_ops().get('cx',0)),
                two_qubit_depth=native.depth(lambda inst:len(inst.qubits)==2))
        rows.append(row);print(json.dumps(row),flush=True)
    result={'qpu_executed':False,'passed':True,'experiments':rows}
    (ROOT/'results/actual_experiment_validation.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
