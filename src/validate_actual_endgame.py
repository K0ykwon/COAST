"""Verify delivered QPY bytes without regenerating or overwriting the circuits."""
import json,hashlib
import numpy as np
from qiskit import qpy,QuantumCircuit
from build_actual_endgame import (ROOT,OUT,N,build_stages,build_B,simulate,circuit,
                                  aer_state,aligned_error,validate)

def main():
    report=json.loads((ROOT/'results/actual_endgame_validation.json').read_text())
    stages,modules,meta=build_stages()
    validate(stages,meta)
    rows=[]
    for name,ops in stages.items():
        row=report['stages'][name];path=OUT/row['qpy_file']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        with path.open('rb') as f:qc=qpy.load(f)[0]
        assert qc.num_qubits==N and not qc.num_parameters
        err=aligned_error(simulate(ops),aer_state(qc));assert err<2e-9
        rows.append({'file':path.name,'max_amplitude_error':err,'sha256_match':True})
    row=report['raw_native_all_to_all'];path=OUT/row['qpy_file']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    with path.open('rb') as f:qc=qpy.load(f)[0]
    assert set(qc.count_ops())<={'rz','sx','x','cx'}
    err=aligned_error(simulate(stages['raw']),aer_state(qc));assert err<2e-8
    rows.append({'file':path.name,'max_amplitude_error':err,'sha256_match':True})
    rng=np.random.default_rng(2049)
    psi=rng.normal(size=2**N)+1j*rng.normal(size=2**N);psi/=np.linalg.norm(psi)
    for name,ops in modules.items():
        if not ops:continue
        path=OUT/f'module_{name}.qpy'
        with path.open('rb') as f:qc=qpy.load(f)[0]
        probe=QuantumCircuit(N);probe.set_statevector(psi);probe.compose(qc,inplace=True)
        err=aligned_error(simulate(ops,psi),aer_state(probe));assert err<2e-9
        rows.append({'file':path.name,'random_input_max_amplitude_error':err})
    result={'passed':True,'files':rows,'scope':'all four stages, native raw and all nonempty propagation modules; QPY loaded from disk'}
    (ROOT/'results/actual_qpy_independent_reload.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
