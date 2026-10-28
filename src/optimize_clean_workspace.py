"""Synthesize COAST endgame circuits with reusable *clean* AND-chain scratch.

The original 13 data wires remain unchanged. All extra wires start and finish
in |0>, even for arbitrary coherent data input. This is a gate synthesis
change, not terminal-list state preparation or a new query-complexity claim.
"""
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, qpy, transpile
from qiskit.circuit.library import RYGate, RCCXGate
from qiskit_aer import AerSimulator

from build_actual_endgame import ROOT, OUT, N, build_stages, simulate, aligned_error

RAW_WORK = 10  # predecessor inverse conditions on board, root, and move prefix
FULL_WORK = 12
RELATIVE = RCCXGate().definition
RELATIVE_INVERSE = RELATIVE.inverse()


def chain_and(qc, controls, work):
    """Return a clean wire containing AND(controls), with its uncompute list."""
    k = len(controls)
    assert k >= 2 and len(work) >= k-1
    sequence = [(controls[0],controls[1],work[0])]
    for j in range(2,k):
        sequence.append((controls[j],work[j-2],work[j-1]))
    for a,b,t in sequence: qc.compose(RELATIVE,[a,b,t],inplace=True)
    return work[k-2],sequence


def uncompute(qc,sequence):
    for a,b,t in reversed(sequence): qc.compose(RELATIVE_INVERSE,[a,b,t],inplace=True)


def controlled_x(qc,cs,target,work):
    k=len(cs)
    if k==0:qc.x(target)
    elif k==1:qc.cx(cs[0],target)
    elif k==2:qc.ccx(cs[0],cs[1],target)
    elif k==3:qc.mcx(cs,target)
    else:
        # Reuse k-2 clean work bits; AND of first k-1 controls.
        flag,sequence=chain_and(qc,cs[:-1],work)
        qc.ccx(flag,cs[-1],target)
        uncompute(qc,sequence)


def controlled_ry(qc,cs,target,theta,work):
    k=len(cs)
    if k==0:qc.ry(theta,target)
    elif k==1:qc.cry(theta,cs[0],target)
    elif k==2:qc.append(RYGate(theta).control(2),cs+[target])
    else:
        flag,sequence=chain_and(qc,cs,work)
        qc.cry(theta,flag,target)
        uncompute(qc,sequence)


def controlled_phase(qc,cs,theta,work):
    k=len(cs)
    if k==0:qc.global_phase+=theta
    elif k==1:qc.p(theta,cs[0])
    elif k<=4:qc.mcp(theta,cs[:-1],cs[-1])
    else:
        flag,sequence=chain_and(qc,cs,work)
        qc.p(theta,flag)
        uncompute(qc,sequence)


def clean_circuit(ops,name,nwork):
    qc=QuantumCircuit(N+nwork,name=name)
    work=list(range(N,N+nwork))
    for op in ops:
        cs=[q for q,_ in op.cond]
        zeros=[q for q,v in op.cond if v==0]
        if zeros:qc.x(zeros)
        if op.kind=='x':controlled_x(qc,cs,op.target,work)
        elif op.kind=='ry':controlled_ry(qc,cs,op.target,op.angle,work)
        elif op.kind=='phase':controlled_phase(qc,cs,op.angle,work)
        elif op.kind=='h':
            if not cs:qc.h(op.target)
            elif len(cs)==1:
                qc.ry(-math.pi/4,op.target)
                qc.cz(cs[0],op.target)
                qc.ry(math.pi/4,op.target)
            else:raise ValueError('controlled-H exceeds one extra control')
        else:raise ValueError(op.kind)
        if zeros:qc.x(zeros)
    qc.metadata={'implementation':'actual endgame propagation; clean AND-chain scratch',
                 'data_qubits':N,'clean_scratch':nwork,'scratch_indices':work,
                 'fixed_fixture':'7x7 freestyle Gomoku, empty cells 7,8,17,33',
                 'all_scratch_return_zero':True,'qpu_executed':False,
                 'note':'local predicate compiler enumerates 3^4 boards; no empty-board scalability claim'}
    return qc


def state(qc,psi=None):
    c=qc.copy()
    if psi is not None:
        init=QuantumCircuit(qc.num_qubits)
        full=np.zeros(2**qc.num_qubits,complex)
        full[:2**N]=psi
        init.set_statevector(full)
        init.compose(c,inplace=True)
        c=init
    c.save_statevector()
    result=AerSimulator(method='statevector',max_parallel_threads=2).run(c).result()
    if not result.success:raise RuntimeError(str(result))
    return np.asarray(result.get_statevector())


def main():
    begin=time.time();OUT.mkdir(parents=True,exist_ok=True)
    stages,_,meta=build_stages()
    ops=stages['raw']
    raw=clean_circuit(ops,f'COAST_G7_E4_raw_clean{N+RAW_WORK}',RAW_WORK)
    path=OUT/f'COAST_G7_E4_raw_clean{N+RAW_WORK}.qpy'
    with path.open('wb') as f:qpy.dump(raw,f)
    with path.open('rb') as f:loaded=qpy.load(f)[0]
    rng=np.random.default_rng(20260926)
    psi=rng.standard_normal(2**N)+1j*rng.standard_normal(2**N)
    psi/=np.linalg.norm(psi)
    checks={}
    for label,input_state in [('zero',None),('coherent_random_data',psi)]:
        actual=state(loaded,input_state)
        expected=simulate(ops,input_state)
        leakage=float(np.sum(abs(actual[2**N:])**2))
        err=aligned_error(expected,actual[:2**N])
        assert leakage<1e-20 and err<2e-10,(label,leakage,err)
        checks[label]=dict(max_data_amplitude_error=err,dirty_work_probability=leakage)
        print('checked logical',label,checks[label],flush=True)
    native=transpile(loaded,basis_gates=['rz','sx','x','cx'],optimization_level=1,seed_transpiler=20260926)
    path_basis=OUT/f'COAST_G7_E4_raw_clean{N+RAW_WORK}_native.qpy'
    with path_basis.open('wb') as f:qpy.dump(native,f)
    with path_basis.open('rb') as f:verified=qpy.load(f)[0]
    native_actual=state(verified)
    expected=simulate(ops)
    native_leakage=float(np.sum(abs(native_actual[2**N:])**2))
    native_err=aligned_error(expected,native_actual[:2**N])
    assert native_err<2e-8 and native_leakage<1e-18,(native_err,native_leakage)
    old=json.loads((ROOT/'results/actual_endgame_validation.json').read_text())
    prior=old['raw_native_all_to_all']
    previous_result_path=ROOT/'results/actual_clean_workspace_optimization.json'
    previous_work_cx=None
    if previous_result_path.exists():
        previous_work_cx=json.loads(previous_result_path.read_text())['raw']['cx']
    row=dict(qubits=loaded.num_qubits,data_qubits=N,clean_work_qubits=RAW_WORK,
             cx=native.count_ops().get('cx',0),two_qubit_depth=native.depth(lambda item:len(item.qubits)==2),
             depth=native.depth(),previous_cx=prior['ops']['cx'],previous_two_qubit_depth=prior['two_qubit_depth'],
             full_toffoli_clean_workspace_cx=previous_work_cx,
             cx_reduction_fraction=1-native.count_ops().get('cx',0)/prior['ops']['cx'],
             checks=checks,native_max_amplitude_error=native_err,native_dirty_work_probability=native_leakage,
             qpy=path.name,native_qpy=path_basis.name,
             qpy_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
             native_qpy_sha256=hashlib.sha256(path_basis.read_bytes()).hexdigest(),
             compute_uncompute='relative-phase Toffoli and exact inverse; phase cancels as controls and scratch are unchanged',
             all_to_all=True,backend_routed=False,qpu_executed=False,
             limitation='This clean-workspace circuit still uses a compiler exponential in empty-cell count.')
    result={'raw':row,'full_pipeline_qubits_with_max_12_work':N+FULL_WORK,
            'pipeline_comparison':'to be evaluated after raw benchmark','elapsed_seconds':time.time()-begin}
    dest=ROOT/'results/actual_clean_workspace_optimization.json'
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
