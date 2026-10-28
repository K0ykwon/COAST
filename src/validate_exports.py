"""Check saved-and-reloaded QPY files, including controlled-QPE phase signs."""
import json,math
import numpy as np
from qiskit import qpy
from qiskit.quantum_info import Statevector
from coast_analysis import ROOT,lines,winner

def load(name):
    with (ROOT/'circuits'/f'{name}.qpy').open('rb') as f:return qpy.load(f)[0]

def main():
    checks=[]
    for name in ('ttt_late','gomoku_four_empty'):
        f=json.loads((ROOT/'results'/f'{name}_fixture.json').read_text());na=f['action_qubits'];nt=f['terminal_qubits'];n=na+nt
        for stage in ('prepare','filter','final'):
            q=load(f'{name}_{stage}');v=Statevector(q).data
            expected=np.array([1/len(f['actions'])]*len(f['actions']) if stage=='prepare' else f['filtered_action_probabilities'] if stage=='filter' else f['final_action_probabilities'])
            observed=(abs(v.reshape((2**nt,2**na)))**2).sum(axis=0)
            error=float(max(abs(observed[:len(expected)]-expected)))
            assert error<1e-8 and observed[len(expected):].sum()<1e-8
            checks.append(dict(circuit=f'{name}_{stage}',check='reloaded root marginal',max_error=error))
        q=load(f'{name}_qpe4');v=Statevector(q.remove_final_measurements(inplace=False)).data
        M=16;observed=(abs(v.reshape((M,2**n)))**2).sum(axis=1);phi=math.asin(math.sqrt(f['q_filtered']))/math.pi
        def dist(ph):
            d=ph-np.arange(M)/M
            return (np.sinc(M*d)/np.sinc(d))**2
        expected=(dist(phi)+dist(1-phi))/2;error=float(max(abs(observed-expected)))
        assert error<1e-8,(name,error)
        checks.append(dict(circuit=f'{name}_qpe4',check='reloaded QPE phase law',max_error=error,phase_distribution=observed.tolist()))
    for i in range(6):
        q=load(f'fpaa_control_{i}_amplified');p=float(abs(Statevector(q).data[1])**2)
        assert p>=1-1e-6-1e-10
        checks.append(dict(circuit=f'fpaa_control_{i}_amplified',check='reloaded amplification response',success=p))
    for name in ('winner7','winner7_fast'):
        q=load(name);assert q.num_qubits<=127
        assert set(q.count_ops())<=set(['rz','sx','x','cx'])
        checks.append(dict(circuit=name,check='reloaded primitive-only width',qubits=q.num_qubits,full_statevector=False))
    out=dict(status='passed',checks=checks,full_127_qubit_preparation_implemented=False,hardware_executed=False)
    (ROOT/'results/export_validation.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
