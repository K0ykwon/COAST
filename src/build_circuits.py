"""Generate real circuits for oracle modules and table-prepared endgame controls.

The full count-free 49-ply preparation B is NOT implemented by this script.
No credentials or hardware execution is needed or performed.
"""
import json, math, platform
from pathlib import Path
from functools import lru_cache
import numpy as np
import scipy
from scipy.optimize import least_squares
import qiskit
from qiskit import QuantumCircuit, QuantumRegister, transpile, qpy
from qiskit.circuit.library import StatePreparation, DiagonalGate, QFTGate
from qiskit.quantum_info import Statevector
from qiskit.transpiler.passes.synthesis import HLSConfig
from coast_analysis import ROOT,lines,winner,terminal

def controlled_inc(qc,controls,bits):
    for j in reversed(range(len(bits))):
        cs=list(controls)+list(bits[:j])
        if cs: qc.mcx(cs,bits[j])
        else: qc.x(bits[j])

def mcx_clean(qc,controls,target,aux):
    k=len(controls)
    if k==0:qc.x(target)
    elif k==1:qc.cx(controls[0],target)
    elif k==2:qc.ccx(controls[0],controls[1],target)
    else:
        assert len(aux)>=k-2
        qc.ccx(controls[0],controls[1],aux[0])
        for i in range(2,k-1):qc.ccx(controls[i],aux[i-2],aux[i-1])
        qc.ccx(controls[-1],aux[k-3],target)
        for i in reversed(range(2,k-1)):qc.ccx(controls[i],aux[i-2],aux[i-1])
        qc.ccx(controls[0],controls[1],aux[0])

def winner_xor_fast(n=7,k=5,player=1):
    ws=lines(n,k);nb=2*n*n;nc=math.ceil(math.log2(len(ws)+1))
    # Reuse clean v-chain scratch across line AND, counter increments, and zero test.
    naux=max(k,nc)-2
    qc=QuantumCircuit(nb+nc+2+naux,name=f'win{player}_fast_{n}x{n}')
    ctr=list(range(nb,nb+nc));out=nb+nc;line=out+1;aux=list(range(line+1,qc.num_qubits))
    scan=QuantumCircuit(qc.num_qubits)
    for w in ws:
        mcx_clean(scan,[2*i+player-1 for i in w],line,aux)
        for j in reversed(range(nc)):mcx_clean(scan,[line]+ctr[:j],ctr[j],aux)
        mcx_clean(scan,[2*i+player-1 for i in w],line,aux)
    qc.compose(scan,inplace=True);qc.x(out);qc.x(ctr);mcx_clean(qc,ctr,out,aux);qc.x(ctr)
    qc.compose(scan.inverse(),inplace=True)
    return qc

def winner_xor(n=7,k=5,player=1):
    ws=lines(n,k);nb=2*n*n;nc=math.ceil(math.log2(len(ws)+1))
    qc=QuantumCircuit(nb+nc+1,name=f'win{player}_{n}x{n}')
    ctr=list(range(nb,nb+nc));out=nb+nc
    scan=QuantumCircuit(qc.num_qubits)
    for w in ws: controlled_inc(scan,[2*i+player-1 for i in w],ctr)
    qc.compose(scan,inplace=True)
    qc.x(out);qc.x(ctr);qc.mcx(ctr,out);qc.x(ctr)
    qc.compose(scan.inverse(),inplace=True)
    return qc

def verify_winner_small(fast=False):
    from itertools import product
    gate=(winner_xor_fast(2,2) if fast else winner_xor(2,2)).to_gate();ws=lines(2,2);nc=math.ceil(math.log2(len(ws)+1))
    for b in product(range(3),repeat=4):
        circuit=QuantumCircuit(gate.num_qubits)
        index=0
        for i,p in enumerate(b):
            if p:index |= 1<<(2*i+p-1);circuit.x(2*i+p-1)
        circuit.append(gate,range(gate.num_qubits))
        target=index+((1<<(8+nc)) if any(all(b[i]==1 for i in w) for w in ws) else 0)
        state=Statevector(circuit)
        assert abs(state.data[target])**2>1-1e-10
    return dict(boards=81,ancillas_restored=True,passed=True)

def terminal_sets(board,n,k):
    ws=lines(n,k);player=1 if board.count(1)==board.count(2) else 2
    @lru_cache(None)
    def rec(b,p):
        if terminal(b,ws):return frozenset([b])
        ts=set()
        for i,v in enumerate(b):
            if not v:
                z=list(b);z[i]=p;ts.update(rec(tuple(z),3-p))
        return frozenset(ts)
    acts=[i for i,v in enumerate(board) if v==0];sets=[]
    for a in acts:
        z=list(board);z[a]=player;sets.append(rec(tuple(z),3-player))
    return player,acts,sets

def fixture_7x7():
    raw=['XXXOXXO','XOXOOXX','OOOXXXX','OXXXOOX','OOXXOOX','OOXXOOO','XOXOOXO']
    draw=tuple(1 if x=='X' else 2 for row in raw for x in row)
    rng=np.random.default_rng(9137)
    for _ in range(3000):
        holes=list(rng.choice([i for i,v in enumerate(draw) if v==1],2,replace=False))+list(rng.choice([i for i,v in enumerate(draw) if v==2],2,replace=False))
        b=tuple(0 if i in holes else v for i,v in enumerate(draw))
        p,acts,sets=terminal_sets(b,7,5)
        g=[sum(winner(t,lines(7,5))==p for t in ts)/len(ts) for ts in sets]
        if 0<sum(g)<len(g) and max(g)-min(g)>.1:return b
    raise RuntimeError('no suitable fixture found')

def zero_phase(qc,phi):
    diagonal=np.ones(2**qc.num_qubits,dtype=complex);diagonal[0]=np.exp(1j*phi)
    qc.append(DiagonalGate(diagonal),range(qc.num_qubits))

def build_reference(board,n,k):
    player,acts,sets=terminal_sets(board,n,k);terms=sorted(set().union(*sets));index={t:i for i,t in enumerate(terms)}
    na=max(1,math.ceil(math.log2(len(acts))));nt=max(1,math.ceil(math.log2(len(terms))));nq=na+nt
    vec=np.zeros(2**nq,dtype=complex)
    for a,ts in enumerate(sets):
        for t in ts:vec[a+(index[t]<<na)]=1/math.sqrt(len(acts)*len(ts))
    A=QuantumCircuit(nq,name='A_table');A.append(StatePreparation(vec),range(nq));Ag=A.to_gate()
    wins=[winner(t,lines(n,k))==player for t in terms]
    def mark(qc,phi):
        diag=np.ones(2**nt,dtype=complex)
        for t,v in enumerate(wins):
            if v:diag[t]=np.exp(1j*phi)
        qc.append(DiagonalGate(diag),range(na,nq))
    def diffuse(qc,gate,phi):
        qc.append(gate.inverse(),range(nq));zero_phase(qc,phi);qc.append(gate,range(nq))
    F=QuantumCircuit(nq,name='F_table');F.append(Ag,range(nq));mark(F,math.pi/2);diffuse(F,Ag,math.pi/2);Fg=F.to_gate()
    good=np.array([wins[t] if t<len(wins) else False for t in range(2**nt) for a in range(2**na)])
    psi=Statevector(F).data;qf=float(np.sum(abs(psi[good])**2));theta=math.asin(math.sqrt(qf));r=max(0,math.floor(math.pi/(4*theta)-.5)) if qf else 0
    final=QuantumCircuit(nq,name='final_exact_calibration');final.append(Fg,range(nq))
    for _ in range(r):mark(final,math.pi);diffuse(final,Fg,math.pi)
    fractional=None
    if 0<qf<1-1e-12:
        base=np.array([math.sqrt(qf),math.sqrt(1-qf)],complex)
        cur=np.array([math.sin((2*r+1)*theta),math.cos((2*r+1)*theta)],complex)
        def residual(x):
            phi,beta=x;sg=np.diag([np.exp(1j*beta),1]);d=np.eye(2)+(np.exp(1j*phi)-1)*np.outer(base,base.conj());v=d@sg@cur
            return [v[1].real,v[1].imag]
        choices=[least_squares(residual,x,gtol=1e-13,xtol=1e-13,ftol=1e-13,max_nfev=3000) for x in ([1.,1.],[3.,1.],[1.,3.],[-2.,2.])]
        sol=min(choices,key=lambda z:np.linalg.norm(z.fun));assert np.linalg.norm(sol.fun)<1e-8
        phi,beta=map(float,sol.x);mark(final,beta);diffuse(final,Fg,phi);fractional=dict(source_phase=phi,target_phase=beta)
    Q=QuantumCircuit(nq,name='Q_calibration');mark(Q,math.pi);diffuse(Q,Fg,math.pi);Q.global_phase+=math.pi
    # Standard 4-bit QPE reference. The 127-wire architecture instead recycles one ancilla.
    m=4;cal=QuantumCircuit(nq+m,m,name='qpe4_reference');cal.append(Fg,range(nq));cal.h(range(nq,nq+m))
    for j in range(m):
        cg=Q.to_gate().control(1)
        for _ in range(2**j):cal.append(cg,[nq+j]+list(range(nq)))
    cal.append(QFTGate(m).inverse(),range(nq,nq+m));cal.measure(range(nq,nq+m),range(m))
    expected_g=np.array([sum(winner(t,lines(n,k))==player for t in ts)/len(ts) for ts in sets]);q=float(expected_g.mean())
    expected_f=(expected_g*(1+4*(1-q)**2)+(1-expected_g)*(1-2*q)**2)/len(acts)
    pf=abs(psi.reshape((2**nt,2**na)))**2;pf=pf.sum(axis=0)[:len(acts)]
    assert np.max(abs(pf-expected_f))<1e-10
    vf=Statevector(final).data;marked=float(np.sum(abs(vf[good])**2));assert marked>1-1e-9 or qf==0
    final_actions=(abs(vf.reshape((2**nt,2**na)))**2).sum(axis=0)[:len(acts)]
    target_final=expected_g/(len(acts)*q) if q else np.ones(len(acts))/len(acts)
    assert max(abs(final_actions-target_final))<1e-8
    @lru_cache(None)
    def minimax(b,p):
        w=winner(b,lines(n,k))
        if w:return 1 if w==p else -1
        if 0 not in b:return 0
        return max(-minimax(tuple(p if j==i else v for j,v in enumerate(b)),3-p) for i,x in enumerate(b) if not x)
    vals=[-minimax(tuple(player if j==a else v for j,v in enumerate(board)),3-player) for a in acts]
    metadata=dict(board=list(board),board_size=n,win_length=k,player=player,actions=acts,action_qubits=na,terminal_qubits=nt,
        minimax_values=vals,optimal_action_codes=[i for i,v in enumerate(vals) if v==max(vals)],
        terminal_boards=[list(t) for t in terms],terminal_counts=[len(s) for s in sets],terminal_ids_by_action=[sorted(index[t] for t in s) for s in sets],g=expected_g.tolist(),q=q,q_filtered=qf,
        filtered_action_probabilities=pf.tolist(),final_action_probabilities=final_actions.tolist(),final_marked_probability=marked,
        calibration_mode='analytic exact reference; QPE circuit exported separately',r=r,fractional=fractional,
        preparation='classically enumerated table; not count-free propagation')
    return {'prepare':A,'filter':F,'final':final,'qpe4':cal},metadata

def save_circuit(name,qc,compile_basis=False):
    path=ROOT/'circuits'/f'{name}.qpy'
    report=dict(qubits=qc.num_qubits,abstract_depth=qc.depth(),abstract_ops=dict(qc.count_ops()),file=path.name)
    compiled=transpile(qc,basis_gates=['rz','sx','x','cx'],optimization_level=1,hls_config=HLSConfig(mcx=['noaux_v24']),seed_transpiler=20260925)
    report['basis_all_to_all']=dict(qubits=compiled.num_qubits,depth=compiled.depth(),cx=int(compiled.count_ops().get('cx',0)),
        two_qubit_depth=compiled.depth(lambda item:len(item.qubits)==2),ops=dict(compiled.count_ops()),routing='none; all-to-all reference, not hardware-native')
    report['serialized_form']='primitive basis; avoids nested custom-controlled-gate QPY ambiguity'
    with path.open('wb') as f:qpy.dump(compiled,f)
    if compile_basis:
        with (ROOT/'circuits'/f'{name}_basis.qpy').open('wb') as f:qpy.dump(compiled,f)
    return report

def main():
    (ROOT/'circuits').mkdir(exist_ok=True)
    report=dict(environment=dict(python=platform.python_version(),qiskit=qiskit.__version__,numpy=np.__version__,scipy=scipy.__version__),winner_test=verify_winner_small(),winner_fast_test=verify_winner_small(True),modules={},references={})
    win=winner_xor();report['modules']['winner7']=save_circuit('winner7',win,True)
    winfast=winner_xor_fast();report['modules']['winner7_fast']=save_circuit('winner7_fast',winfast,True)
    for name,b,n,k in [('ttt_late',(1,2,1,2,1,0,0,0,2),3,3),('gomoku_four_empty',fixture_7x7(),7,5)]:
        circuits,meta=build_reference(b,n,k);rr={}
        for stage,qc in circuits.items():rr[stage]=save_circuit(f'{name}_{stage}',qc,stage!='qpe4')
        (ROOT/'results'/f'{name}_fixture.json').write_text(json.dumps(meta,indent=2)+'\n')
        report['references'][name]=rr
    (ROOT/'results'/'circuit_resources.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
