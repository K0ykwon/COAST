"""One-qubit controls for the calibrated YLC response; not a game preparation."""
import math,json
from qiskit import QuantumCircuit,qpy,transpile
from qiskit.quantum_info import Statevector
from coast_analysis import ROOT

def main():
    calibration=json.loads((ROOT/'results/gomoku_calibration.json').read_text());s=calibration['schedule']
    rows=[]
    for i,p in enumerate([s['p_lower'],.0626,.1,.5,.9,1.]):
        angle=2*math.asin(math.sqrt(p));base=QuantumCircuit(1,name=f'B_control_{i}');base.ry(angle,0)
        qc=base.copy(name=f'YLC_control_{i}');qc.barrier()
        for alpha,beta in zip(s['alpha'],s['beta']):
            qc.p(beta,0);qc.barrier();qc.ry(-angle,0);qc.barrier();qc.x(0);qc.p(-alpha,0);qc.x(0);qc.barrier();qc.ry(angle,0);qc.barrier();qc.global_phase+=math.pi
        success=float(abs(Statevector(qc).data[1])**2);assert success>=1-s['delta']**2-1e-10
        for kind,circuit in [('baseline',base),('amplified',qc)]:
            with (ROOT/'circuits'/f'fpaa_control_{i}_{kind}.qpy').open('wb') as f:qpy.dump(circuit,f)
        b=transpile(qc,basis_gates=['rz','sx','x','cx'],optimization_level=0)
        rows.append(dict(index=i,input_probability=p,ideal_success=success,qubits=1,basis_ops=dict(b.count_ops()),
                         note='A Ry preparation isolates the fixed-point response; no Gomoku oracle or state preparation'))
    (ROOT/'results/fpaa_controls.json').write_text(json.dumps(dict(K=s['K'],rows=rows),indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
