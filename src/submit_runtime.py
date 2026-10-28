"""Device compilation; submission requires an explicit --execute flag.

Uses an IBM account already saved by the user; never embeds tokens.
No hardware calls were made while creating this package.
"""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from qiskit import qpy
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from coast_analysis import ROOT

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--backend',required=True)
    p.add_argument('--fixture',choices=['ttt_late','gomoku_four_empty'],default='ttt_late')
    p.add_argument('--stage',choices=['prepare','filter','final'],default='filter')
    p.add_argument('--qpy',type=Path,help='Optional standalone circuit; fixture-specific decoding does not apply')
    p.add_argument('--shots',type=int,default=8192)
    p.add_argument('--execute',action='store_true')
    args=p.parse_args()
    from qiskit_ibm_runtime import QiskitRuntimeService,SamplerV2
    backend=QiskitRuntimeService().backend(args.backend)
    source=args.qpy if args.qpy else ROOT/'circuits'/f'{args.fixture}_{args.stage}.qpy'
    with source.open('rb') as f:qc=qpy.load(f)[0]
    if args.qpy and qc.metadata and qc.metadata.get('implementation')=='actual endgame propagation; local predicate compiler':
        from optimize_actual_synthesis import recover_rotations
        qc=recover_rotations(qc)
    qc.measure_all()
    pm=generate_preset_pass_manager(backend=backend,optimization_level=1,seed_transpiler=20260925)
    isa=pm.run(qc)
    active={isa.find_bit(q).index for inst in isa.data if inst.operation.name not in ('barrier','delay') for q in inst.qubits}
    # Transpilers may pad to the device width. Limit actually touched physical qubits.
    if len(active)>127:raise RuntimeError(f'Physical allocation exceeds 127: {len(active)}')
    twoq=sum(len(inst.qubits)==2 for inst in isa.data)
    report=dict(status='compiled_not_submitted',backend=backend.name,fixture=None if args.qpy else args.fixture,stage=args.stage,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),logical_qubits=qc.num_qubits,
        active_physical_qubits=len(active),active_physical_indices=sorted(active),padded_circuit_width=isa.num_qubits,
        native_2q_gates=twoq,native_2q_depth=isa.depth(lambda item:len(item.qubits)==2),ops=dict(isa.count_ops()),shots=args.shots,
        layout=str(isa.layout),calibration_mode='exact analytic reference' if args.stage=='final' and not args.qpy else 'not applicable',
        timestamp=datetime.now(timezone.utc).isoformat())
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest=ROOT/'results'/f'runtime_{args.fixture}_{args.stage}_{stamp}.json'
    if args.execute:
        job=SamplerV2(mode=backend).run([isa],shots=args.shots)
        report.update(status='submitted',job_id=job.job_id());dest.write_text(json.dumps(report,indent=2))
        result=job.result();counts=result[0].data.meas.get_counts()
        report.update(status='completed',counts=counts)
    dest.write_text(json.dumps(report,indent=2)+'\n');print(dest);print(json.dumps({k:v for k,v in report.items() if k!='counts'},indent=2))

if __name__=='__main__':main()
