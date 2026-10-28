"""Decode actual BOARD-register counts; do not use terminal-ID reference decoder."""
import argparse,json,math
from build_actual_endgame import ROOT,N,BOARD,HOLES,PLAYER,decode,full,WS,winner
from build_circuits import terminal_sets

def wilson(k,n,z=1.959963984540054):
    if not n:return None
    p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]

def summarize(counts,clean_work=0):
    _,_,sets=terminal_sets(BOARD,7,5)
    hist=[0]*4;flags=[0]*4;valid=[0]*4;good=[0]*4
    bad_board=dirty_move=dirty_work=off_support=total=0
    for key,c in counts.items():
        c=int(c)
        if c<0:raise ValueError('Counts must be nonnegative')
        key=key.replace(' ','');idx=int(key,16) if key.startswith('0x') else int(key,2)
        if idx>=2**(N+clean_work):raise ValueError('Bit width exceeds the configured circuit; use --clean-work or --calibration')
        work=idx>>N
        if work:dirty_work+=c
        idx &= (1<<N)-1
        a,b,m,f=decode(idx);total+=c;hist[a]+=c;flags[a]+=c*f
        invalid=-1 in b
        if invalid:bad_board+=c
        if m:dirty_move+=c
        supported=not invalid and full(b) in sets[a]
        if not supported:off_support+=c
        if supported and not m and not work:
            valid[a]+=c
            if f and winner(full(b),WS)==PLAYER:good[a]+=c
    if not total:raise ValueError('Empty counts')
    return dict(shots=total,action_counts=hist,action_probabilities=[v/total for v in hist],
        action_intervals_95=[wilson(v,total) for v in hist],flag_counts=flags,
        flag_probability_given_action=[f/h if h else None for f,h in zip(flags,hist)],
        flag_intervals_given_action_95=[wilson(f,h) for f,h in zip(flags,hist)],
        valid_terminal_counts=valid,marked_counts=good,marked_probability=sum(good)/total,
        marked_interval_95=wilson(sum(good),total),invalid_board_counts=bad_board,
        dirty_move_counts=dirty_move,dirty_work_counts=dirty_work,off_support_counts=off_support,
        note='Unconditional denominators; no postselection. Invalid categories may overlap.')

def main():
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output')
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--calibration',action='store_true',help='Read ancillary bit 13 of calibration_Q1')
    mode.add_argument('--reference-qpy',help='Compare full bitstring distributions for root/prefix/echo controls')
    p.add_argument('--clean-work',type=int,default=0,choices=(0,10,12),help='Set 10 for the 23-qubit optimized B circuit')
    a=p.parse_args();data=json.load(open(a.input));counts=data.get('counts',data)
    if a.calibration:
        n=sum(counts.values());k=0
        for key,c in counts.items():
            key=key.replace(' ','');idx=int(key,16) if key.startswith('0x') else int(key,2)
            if idx>=2**(N+1):raise ValueError('Expected <=14 bits')
            k+=c*((idx>>N)&1)
        if not n:raise ValueError('Empty counts')
        out=dict(shots=n,q_filtered_estimate=k/n,interval_95=wilson(k,n),ancilla_bit=N)
    elif a.reference_qpy:
        from qiskit import qpy
        import numpy as np
        from build_actual_endgame import aer_state
        with open(a.reference_qpy,'rb') as f:qc=qpy.load(f)[0]
        expected=abs(aer_state(qc))**2;observed=np.zeros_like(expected)
        for key,c in counts.items():
            z=key.replace(' ','');idx=int(z,16) if z.startswith('0x') else int(z,2)
            if c<0 or idx>=len(observed):raise ValueError('Invalid count or bit width')
            observed[idx]+=c
        n=int(observed.sum())
        if not n:raise ValueError('Empty counts')
        observed/=n;ids=np.arange(len(expected))
        out=dict(shots=n,reference=a.reference_qpy,
            total_variation_distance=float(.5*np.sum(abs(observed-expected))),
            observed_qubit_one_probabilities=[float(observed[(ids>>i)&1==1].sum()) for i in range(qc.num_qubits)],
            ideal_qubit_one_probabilities=[float(expected[(ids>>i)&1==1].sum()) for i in range(qc.num_qubits)],
            note='Full bitstring comparison without terminal-board assumptions; raw frequencies, no postselection')
    else:out=summarize(counts,clean_work=a.clean_work)
    text=json.dumps(out,indent=2)
    if a.output:open(a.output,'w').write(text+'\n')
    print(text)

if __name__=='__main__':main()
