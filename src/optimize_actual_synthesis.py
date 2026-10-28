"""Recover multi-controlled Ry from its portable four-gate QPY encoding.

RY(t/2), MCX, RY(-t/2), MCX = controlled-RY(t). Recovering this
identity enables Qiskit's dedicated controlled-rotation synthesis before
backend routing. The saved portable QPY needs only standard built-in gates.
"""
import json,hashlib
from collections import Counter
import numpy as np
from qiskit import QuantumCircuit,qpy,transpile
from qiskit.circuit.library import RYGate
from qiskit.transpiler.passes.synthesis import HLSConfig
from build_actual_endgame import ROOT,OUT,N,build_stages,simulate,aer_state,aligned_error

def recover_rotations(qc):
    out=qc.copy_empty_like();i=0;data=qc.data
    while i<len(data):
        if i+3<len(data):
            a,b,c,d=data[i:i+4]
            if (a.operation.name==c.operation.name=='ry' and
                b.operation.name==d.operation.name and b.operation.name in ('cx','ccx','mcx') and
                a.qubits==c.qubits and b.qubits==d.qubits and a.qubits[0]==b.qubits[-1] and
                float(a.operation.params[0])==-float(c.operation.params[0])):
                out.append(RYGate(2*float(a.operation.params[0])).control(len(b.qubits)-1),b.qubits)
                i+=4;continue
        out.append(data[i]);i+=1
    return out

def native_compile(qc,level=1):
    return transpile(recover_rotations(qc),basis_gates=['rz','sx','x','cx'],optimization_level=level,
                     hls_config=HLSConfig(mcx=['noaux_v24']),seed_transpiler=20260926)

def main():
    p=ROOT/'results/actual_endgame_validation.json';report=json.loads(p.read_text())
    with (OUT/'COAST_G7_E4_raw.qpy').open('rb') as f:raw=qpy.load(f)[0]
    old=report['raw_native_all_to_all']
    native=native_compile(raw)
    path=OUT/'COAST_G7_E4_raw_native.qpy'
    with path.open('wb') as f:qpy.dump(native,f)
    with path.open('rb') as f:loaded=qpy.load(f)[0]
    stages,_,_=build_stages();err=aligned_error(simulate(stages['raw']),aer_state(loaded));assert err<2e-8
    rng=np.random.default_rng(771)
    psi=rng.normal(size=2**N)+1j*rng.normal(size=2**N);psi/=np.linalg.norm(psi)
    probe=QuantumCircuit(N);probe.set_statevector(psi);probe.compose(loaded,inplace=True)
    random_err=aligned_error(simulate(stages['raw'],psi),aer_state(probe));assert random_err<2e-8
    row=dict(qubits=native.num_qubits,depth=native.depth(),two_qubit_depth=native.depth(lambda inst:len(inst.qubits)==2),
             ops=dict(native.count_ops()),qpy_file=path.name,roundtrip_max_amplitude_error=err,
             random_input_max_amplitude_error=random_err,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
             routing='none; all-to-all reference, not backend ISA',
             optimization='restore controlled-Ry then use dedicated no-ancilla synthesis')
    if 'optimization' not in old:
        report['raw_native_before_rotation_recovery']=old
    report['raw_native_all_to_all']=row
    # Per-gate expansion counts for complete stages. This is a constructive
    # all-to-all resource baseline; no optimization between adjacent gates.
    costs={};resources={}
    for stage in ('raw','fpaa','filter','final'):
        with (OUT/f'COAST_G7_E4_{stage}.qpy').open('rb') as f:qc=recover_rotations(qpy.load(f)[0])
        grouped=Counter();examples={}
        for inst in qc.data:
            op=inst.operation;key=(op.name,op.num_qubits,tuple(float(x) for x in op.params))
            grouped[key]+=1;examples[key]=op
        total_cx=0
        for key,count in grouped.items():
            if key not in costs:
                c=QuantumCircuit(examples[key].num_qubits);c.append(examples[key],range(c.num_qubits))
                t=transpile(c,basis_gates=['rz','sx','x','cx'],optimization_level=0,
                            hls_config=HLSConfig(mcx=['noaux_v24']))
                costs[key]=int(t.count_ops().get('cx',0))
            total_cx+=count*costs[key]
        resources[stage]={'qubits':N,'cx_by_independent_gate_expansion':total_cx,
                          'interpretation':'explicit decomposition cost, no cross-gate optimization or device routing; not measured hardware count'}
    report['all_stage_synthesis_baseline']=resources
    p.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'raw_optimized':row,'stage_resources':resources},indent=2))

if __name__=='__main__':main()
