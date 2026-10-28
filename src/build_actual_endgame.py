"""Executable COAST propagation for a fixed 7x7, four-empty-cell endgame.

The compiler enumerates LOCAL predicate inputs (3**E), not terminal descendants.
DFS terminal sets are imported only in validate(). This is a small-instance
implementation, not a polynomial compiler for the empty 49-cell board.
Qubit order (little endian): action[0:2], board[2:10], move[10:12], flag[12].
"""
import json, math, platform, hashlib, time
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from collections import Counter
import numpy as np
import scipy
from scipy.optimize import least_squares
import qiskit, qiskit_aer
from qiskit import QuantumCircuit, qpy, transpile
from qiskit.transpiler.passes.synthesis import HLSConfig
from qiskit_aer import AerSimulator
from coast_analysis import ROOT, lines, winner, terminal, schedule

OUT = ROOT / 'circuits' / 'actual_endgame'
N = 13
A = (0, 1)
BITS = tuple(range(2, 10))
MOVE = (10, 11)
FLAG = 12
BOARD = (1,1,1,2,1,1,2, 0,0,1,2,2,1,1, 2,2,2,0,1,1,1,
         2,1,1,1,2,2,1, 2,2,1,1,2,0,1, 2,2,1,1,2,2,2, 1,2,1,2,2,1,2)
HOLES = (7, 8, 17, 33)
PLAYER = 2
WS = lines(7, 5)

@dataclass(frozen=True)
class Op:
    kind: str
    cond: tuple = ()
    target: int = -1
    angle: float = 0.

def pattern(bits, val):
    return tuple((q, (val >> j) & 1) for j, q in enumerate(bits))

def board_int(b):
    return sum((1 << (2*i+p-1)) for i,p in enumerate(b) if p)

def bp(b):
    return pattern(BITS, board_int(b))

def full(b):
    z = list(BOARD)
    for i,p in zip(HOLES,b): z[i] = p
    return tuple(z)

@lru_cache(None)
def is_terminal(b): return terminal(full(b), WS)

@lru_cache(None)
def won(b): return winner(full(b), WS)

def inv(ops):
    return [Op(o.kind,o.cond,o.target,-o.angle if o.kind in ('ry','phase') else o.angle)
            for o in reversed(ops)]

def subset_prep(values, cond=()):
    """Uniform nonnegative subset of move addresses, using a binary Ry tree."""
    values = tuple(sorted(values)); assert values
    ops = []
    for bit in reversed(range(len(MOVE))):
        for prefix in sorted({v >> (bit+1) for v in values}):
            vs = [v for v in values if v >> (bit+1) == prefix]
            ones = sum((v >> bit) & 1 for v in vs)
            if not ones: continue
            controls = cond + tuple((MOVE[j],(prefix >> (j-bit-1)) & 1)
                                    for j in range(bit+1,len(MOVE)))
            ops.append(Op('ry',controls,MOVE[bit],2*math.asin(math.sqrt(ones/len(vs)))))
    return ops

def build_B():
    configs = tuple(product(range(3),repeat=4))
    alpha = 1.; beta = {1:1.}
    for d in range(1,4):
        beta[d+1] = alpha/math.sqrt(4-d)
        alpha = beta[d+1]*math.sqrt((d+1)//2)
    gamma = min(beta.values())
    ops = []
    for a in range(4): ops.append(Op('x',pattern(A,a),2+2*a+PLAYER-1))
    for a in range(4):
        b = tuple(PLAYER if i==a else 0 for i in range(4))
        if is_terminal(b):
            ops.append(Op('ry',bp(b)+pattern(A,a),FLAG,2*math.asin(gamma)))
    modules = {'root':list(ops)}
    stages = [{'ply':1,'cumulative_ops':len(ops)}]
    for k in range(2,5):
        last = PLAYER if k%2 else 3-PLAYER
        parents = [b for b in configs if b.count(PLAYER)==k//2 and
                   b.count(3-PLAYER)==(k-1)//2 and not is_terminal(b)]
        select=[]; write=[]; unselect=[]; attenuate=[]
        for b in parents:
            empty = [i for i,x in enumerate(b) if x==0]
            select += subset_prep(empty,bp(b))
            for i in empty:
                target = 2+2*i+last-1
                # A swap on one board bit is reversible. The move address
                # distinguishes disjoint parent-child edges at this layer.
                cond = tuple((q,v) for q,v in bp(b) if q!=target)+pattern(MOVE,i)
                write.append(Op('x',cond,target))
        children = [b for b in configs if b.count(PLAYER)==(k+1)//2 and b.count(3-PLAYER)==k//2]
        for b in children:
            for a in range(4):
                if b[a]!=PLAYER: continue
                preds=[]
                for i,p in enumerate(b):
                    if i==a or p!=last: continue
                    z=list(b);z[i]=0
                    if not is_terminal(tuple(z)): preds.append(i)
                if not preds: continue
                cond=bp(b)+pattern(A,a)
                unselect += inv(subset_prep(preds,cond))
                if is_terminal(b):
                    sine=gamma/(beta[k]*math.sqrt(len(preds)))
                    assert sine<=1+1e-12
                    attenuate.append(Op('ry',cond,FLAG,2*math.asin(min(1,sine))))
        for label,seq in [('select',select),('write',write),('unselect',unselect),('attenuate',attenuate)]:
            modules[f'ply{k}_{label}']=seq
            ops += seq
        stages.append({'ply':k,'cumulative_ops':len(ops),'parents':len(parents)})
    return ops,modules,dict(gamma=gamma,gamma_squared=gamma**2,beta=beta,layers=stages)

def mark(angle):
    # Compile the outcome predicate over local board inputs, without DFS lists.
    return [Op('phase',bp(b)+((FLAG,1),),angle=angle)
            for b in product(range(3),repeat=4) if won(b)==PLAYER]

def zero_phase(bits, angle):
    return [Op('phase',tuple((q,0) for q in bits),angle=angle)]

def build_stages():
    raw,modules,meta=build_B()
    s=schedule(meta['gamma_squared'],.001)
    s.pop('flag_oracle_calls')  # This implementation already retains the flag.
    s['success_flag_phase_gates']=len(s['alpha'])
    root=[Op('h',target=q) for q in A]
    amplified=root+raw
    for alpha,beta in zip(s['alpha'],s['beta']):
        amplified += [Op('phase',((FLAG,1),),angle=beta)] + inv(raw)
        amplified += zero_phase(tuple(range(2,N)),-alpha)+raw
        amplified += [Op('phase',angle=math.pi)]
    filtered=amplified+mark(math.pi/2)+inv(amplified)+zero_phase(tuple(range(N)),math.pi/2)+amplified
    vf=simulate(filtered); good=good_mask(); qf=float(np.sum(abs(vf[good])**2))
    theta=math.asin(math.sqrt(qf)); r=max(0,math.floor(math.pi/(4*theta)-.5))
    final=list(filtered)
    for _ in range(r):
        final += mark(math.pi)+inv(filtered)+zero_phase(tuple(range(N)),math.pi)+filtered
    base=np.array([math.sqrt(qf),math.sqrt(1-qf)],complex)
    cur=np.array([math.sin((2*r+1)*theta),math.cos((2*r+1)*theta)],complex)
    def residual(x):
        phi,beta=x
        d=np.eye(2)+(np.exp(1j*phi)-1)*np.outer(base,base.conj())
        z=d@np.diag([np.exp(1j*beta),1])@cur
        return [z[1].real,z[1].imag]
    sol=least_squares(residual,[1.,1.],gtol=1e-13,xtol=1e-13,ftol=1e-13)
    assert np.linalg.norm(sol.fun)<1e-10
    phi,beta=map(float,sol.x)
    final += mark(beta)+inv(filtered)+zero_phase(tuple(range(N)),phi)+filtered
    meta.update(schedule=s,analytic_q_filtered=qf,integer_iterations=r,
                fractional_phases=dict(source=phi,target=beta),
                calibration_mode='ideal statevector calibration; no QPU estimate or QPU execution')
    return {'raw':root+raw,'fpaa':amplified,'filter':filtered,'final':final},modules,meta

@lru_cache(None)
def matching(cond, target, n=N):
    ids=np.arange(2**n,dtype=np.int64)
    mask=sum(1<<q for q,v in cond); value=sum(v<<q for q,v in cond)
    ok=(ids & mask)==value
    if target>=0: ok &= (ids & (1<<target))==0
    return ids[ok]

def simulate(ops, state=None, n=N):
    """Independent NumPy controlled-gate interpreter, not Qiskit simulation."""
    v=np.zeros(2**n,complex) if state is None else np.array(state,complex,copy=True)
    if state is None: v[0]=1
    for o in ops:
        i=matching(o.cond,o.target,n)
        if o.kind=='phase': v[i]*=np.exp(1j*o.angle); continue
        j=i+(1<<o.target); a=v[i].copy();b=v[j].copy()
        if o.kind=='x': v[i]=b;v[j]=a
        elif o.kind=='h': v[i]=(a+b)/math.sqrt(2);v[j]=(a-b)/math.sqrt(2)
        elif o.kind=='ry':
            c=math.cos(o.angle/2);s=math.sin(o.angle/2)
            v[i]=c*a-s*b;v[j]=s*a+c*b
        else: raise ValueError(o.kind)
    return v

def decode(index):
    vals=[]
    for i in range(4):
        two=(index>>(2+2*i))&3
        vals.append({0:0,1:1,2:2,3:-1}[two])
    return index&3,tuple(vals),(index>>10)&3,(index>>12)&1

@lru_cache(None)
def good_mask():
    return np.array([bool(f and m==0 and -1 not in b and won(b)==PLAYER)
                     for a,b,m,f in map(decode,range(2**N))])

def circuit(ops,name,n=N):
    qc=QuantumCircuit(n,name=name)
    for o in ops:
        zeros=[q for q,v in o.cond if v==0]; cs=[q for q,v in o.cond]
        if zeros: qc.x(zeros)
        if o.kind=='h':
            if len(cs)==1:
                qc.ry(-math.pi/4,o.target);qc.cz(cs[0],o.target);qc.ry(math.pi/4,o.target)
            elif not cs: qc.h(o.target)
            else: raise ValueError('H supports at most one extra control')
        elif o.kind=='x':
            if cs: qc.mcx(cs,o.target)
            else: qc.x(o.target)
        elif o.kind=='ry':
            if cs:
                # Exact identity: RY(theta/2), MCX, RY(-theta/2), MCX.
                # Only built-in gates are serialized; no custom gate payloads.
                qc.ry(o.angle/2,o.target);qc.mcx(cs,o.target)
                qc.ry(-o.angle/2,o.target);qc.mcx(cs,o.target)
            else: qc.ry(o.angle,o.target)
        elif o.kind=='phase':
            if len(cs)>1: qc.mcp(o.angle,cs[:-1],cs[-1])
            elif cs: qc.p(o.angle,cs[0])
            else: qc.global_phase+=o.angle
        if zeros: qc.x(zeros)
    qc.metadata={'implementation':'actual endgame propagation; local predicate compiler',
                 'fixed_board':list(BOARD),'holes':list(HOLES),'root_player':PLAYER,
                 'action_bits':list(A),'board_bits':list(BITS),'move_bits':list(MOVE),
                 'success_flag':FLAG,'stage':name,'measurement_order':'little endian q_i -> classical bit i',
                 'full_empty_board_implementation':False}
    return qc

def aer_state(qc):
    c=qc.copy();c.save_statevector()
    result=AerSimulator(method='statevector',max_parallel_threads=2).run(c).result()
    if not result.success: raise RuntimeError(str(result))
    return np.asarray(result.get_statevector())

def fidelity(a,b): return float(abs(np.vdot(a,b))**2)

def aligned_error(a,b):
    phase=np.vdot(a,b)
    return float(np.max(abs(a-b*phase.conjugate()/abs(phase))))

def validate(stages,meta):
    from build_circuits import terminal_sets  # independent oracle, validation ONLY
    _,_,sets=terminal_sets(BOARD,7,5)
    raw=simulate(stages['raw']); g2=meta['gamma_squared']
    targets={a|((board_int(tuple(t[i] for i in HOLES)))<<2)|(1<<FLAG)
             for a,ts in enumerate(sets) for t in ts}
    expected_amp=meta['gamma']/2
    assert max(abs(raw[i]-expected_amp) for i in targets)<1e-12
    other_flag=[i for i in range(2**N) if i&(1<<FLAG) and i not in targets]
    leakage=float(np.sum(abs(raw[other_flag])**2));assert leakage<1e-24
    per_root=[]
    for a,ts in enumerate(sets):
        ids=[i for i in targets if i&3==a]
        p=float(np.sum(abs(raw[ids])**2)*4)
        assert abs(p-g2*len(ts))<1e-12
        per_root.append(dict(action=a,site=HOLES[a],terminal_count=len(ts),raw_flag_probability=p,
                             win_fraction=sum(winner(t,WS)==PLAYER for t in ts)/len(ts)))
    invalid=np.array([m!=0 or -1 in b or not is_terminal(b) or b[a]!=PLAYER
                      for a,b,m,f in map(decode,range(2**N))])
    report={'terminal_set_equality':True,'distinct_root_terminal_pairs':len(targets),
            'raw_flag_off_target_probability':leakage,'raw_success_amplitude_max_error':float(max(abs(raw[i]-expected_amp) for i in targets)),
            'per_root':per_root,'stages':{}}
    for name,ops in stages.items():
        v=simulate(ops);probs=abs(v)**2
        bad=float(probs[invalid].sum());assert bad<1e-20
        ap=[float(probs[np.arange(2**N)%4==a].sum()) for a in range(4)]
        fp=[float(probs[[i for i in range(2**N) if i&3==a and i&(1<<FLAG)]].sum())/ap[a] for a in range(4)]
        row=dict(norm=float(probs.sum()),action_probabilities=ap,flag_probability_given_action=fp,
                 marked_probability=float(probs[good_mask()].sum()),invalid_or_dirty_move_probability=bad,
                 abstract_operations=len(ops))
        assert abs(probs.sum()-1)<1e-10
        if name=='fpaa':
            assert min(fp)>=1-meta['schedule']['delta']**2-1e-10
            assert max(abs(np.array(ap)-.25))<1e-10
        if name=='final':
            assert row['marked_probability']>1-1e-10
            assert max(abs(np.array(ap)-[.4,.2,.2,.2]))<2e-6
        back=simulate(inv(ops),v)
        assert abs(back[0])**2>1-1e-10
        row['inverse_zero_return_probability']=float(abs(back[0])**2)
        report['stages'][name]=row
    return report

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    started=time.time(); stages,modules,meta=build_stages()
    report=validate(stages,meta)
    report.update(environment=dict(python=platform.python_version(),qiskit=qiskit.__version__,
                  qiskit_aer=qiskit_aer.__version__,numpy=np.__version__,scipy=scipy.__version__),
                  logical_qubits=N,metadata=meta,qpu_executed=False)
    for name,ops in stages.items():
        qc=circuit(ops,'COAST_G7_E4_'+name)
        path=OUT/f'COAST_G7_E4_{name}.qpy'
        with path.open('wb') as f:qpy.dump(qc,f)
        with path.open('rb') as f:loaded=qpy.load(f)[0]
        expected=simulate(ops); actual=aer_state(loaded)
        err=aligned_error(expected,actual);fid=fidelity(expected,actual)
        assert err<2e-9 and abs(fid-1)<2e-8,(name,err,fid)
        # Also check a nonzero coherent input: this tests the full unitary,
        # rather than only its action on the intended prepared state.
        rng=np.random.default_rng(20260926)
        random_state=rng.normal(size=2**N)+1j*rng.normal(size=2**N)
        random_state/=np.linalg.norm(random_state)
        probe=QuantumCircuit(N);probe.set_statevector(random_state);probe.compose(loaded,inplace=True)
        probe_expected=simulate(ops,random_state)
        probe_actual=aer_state(probe)
        probe_err=aligned_error(probe_expected,probe_actual);assert probe_err<2e-9
        row=report['stages'][name]
        row.update(qpy_file=path.name,qpy_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   qpy_roundtrip_fidelity=fid,qpy_roundtrip_max_amplitude_error=err,
                   coherent_random_input_max_amplitude_error=probe_err,
                   circuit_depth=loaded.depth(),circuit_operations=dict(loaded.count_ops()))
        print(json.dumps({'stage':name,**row}),flush=True)
    # Native decomposition of the entire raw propagation, with no extra qubits.
    rawq=circuit(stages['raw'],'COAST_G7_E4_raw_native')
    native=transpile(rawq,basis_gates=['rz','sx','x','cx'],optimization_level=1,
                     hls_config=HLSConfig(mcx=['noaux_v24']),seed_transpiler=20260926)
    native_path=OUT/'COAST_G7_E4_raw_native.qpy'
    with native_path.open('wb') as f:qpy.dump(native,f)
    with native_path.open('rb') as f:native_loaded=qpy.load(f)[0]
    native_err=aligned_error(simulate(stages['raw']),aer_state(native_loaded))
    assert native_err<2e-8
    report['raw_native_all_to_all']=dict(qubits=native.num_qubits,depth=native.depth(),
        two_qubit_depth=native.depth(lambda inst:len(inst.qubits)==2),ops=dict(native.count_ops()),
        qpy_file=native_path.name,roundtrip_max_amplitude_error=native_err,
        sha256=hashlib.sha256(native_path.read_bytes()).hexdigest(),
        routing='none; all-to-all resource reference, not backend ISA')
    # Persist small, separately runnable primitive modules for a staged QPU plan.
    report['modules']={}
    for name,ops in modules.items():
        if not ops: continue
        qc=circuit(ops,'module_'+name)
        path=OUT/f'module_{name}.qpy'
        with path.open('wb') as f:qpy.dump(qc,f)
        report['modules'][name]=dict(file=path.name,operations=len(ops))
    report['elapsed_seconds']=time.time()-started
    report['all_checks_passed']=True
    dest=ROOT/'results'/'actual_endgame_validation.json'
    dest.write_text(json.dumps(report,indent=2)+'\n')
    print('PASSED',dest,flush=True)

if __name__=='__main__':main()
