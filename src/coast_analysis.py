"""Reproduce COAST theory checks; no quantum backend calls."""
import json, math, sys, random, bisect
from pathlib import Path
from functools import lru_cache
from itertools import product
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def lines(n, k):
    out=[]
    for dr,dc in ((0,1),(1,0),(1,1),(1,-1)):
        for r in range(n):
            for c in range(n):
                xy=[(r+j*dr,c+j*dc) for j in range(k)]
                if all(0<=a<n and 0<=b<n for a,b in xy):
                    out.append(tuple(n*a+b for a,b in xy))
    return out

def winner(board, ws):
    for w in ws:
        p=board[w[0]]
        if p and all(board[i]==p for i in w): return p
    return 0

def terminal(board,ws): return bool(winner(board,ws) or 0 not in board)

def first_hit(board, ws, root, last):
    own=[set(w) for w in ws if all(board[i]==last for i in w)]
    opp=any(all(board[i]==3-last for i in w) for w in ws)
    return (bool(own) and not opp and bool(set.intersection(*own)-{root})) or (0 not in board and not own and not opp)

def schedule(p_lb,delta):
    """YLC: amplitude failure <= delta; K odd, (K-1)/2 iterates."""
    if not 0<p_lb<=1 or not 0<delta<1: raise ValueError('invalid bound/tolerance')
    K=1 if p_lb==1 else max(1,math.ceil(math.acosh(1/delta)/math.atanh(math.sqrt(p_lb))))
    if K%2==0: K+=1
    g=1/math.cosh(math.acosh(1/delta)/K)
    alpha=[2*math.atan2(1,math.tan(2*math.pi*j/K)*math.sqrt(1-g*g)) for j in range(1,(K-1)//2+1)]
    beta=[-v for v in alpha[::-1]]
    return dict(p_lower=p_lb,delta=delta,K=K,iterates=(K-1)//2,raw_preparation_calls=K,
                flag_oracle_calls=K-1,width_parameter=1-g*g,alpha=alpha,beta=beta)

def validate_schedule(s):
    worst=0; error=0
    for p in np.linspace(s['p_lower'],1,2001):
        v=np.array([math.sqrt(1-p),math.sqrt(p)],complex);psi=v.copy()
        for a,b in zip(s['alpha'],s['beta']):
            st=np.diag([1,np.exp(1j*b)])
            ss=np.eye(2)+(np.exp(-1j*a)-1)*np.outer(psi,psi.conj())
            v=-ss@st@v
        failure=abs(v[0])**2
        x=math.cosh(math.acosh(1/s['delta'])/s['K'])*math.sqrt(1-p)
        target=s['delta']**2*math.cos(s['K']*math.acos(min(1,max(-1,x))))**2
        worst=max(worst,failure);error=max(error,abs(failure-target))
    assert worst<=s['delta']**2+1e-11
    assert error<1e-11
    return dict(max_failure_grid=worst,max_polynomial_error=error,grid_points=2001)

def analyze_ttt():
    ws=lines(3,3)
    @lru_cache(None)
    def descendants(b,p):
        if terminal(b,ws): return frozenset([b])
        acc=set()
        for i,v in enumerate(b):
            if not v:
                z=list(b);z[i]=p;acc.update(descendants(tuple(z),3-p))
        return frozenset(acc)
    @lru_cache(None)
    def minimax(b,p):
        w=winner(b,ws)
        if w:return 1 if w==p else -1
        if 0 not in b:return 0
        return max(-minimax(tuple(p if j==i else v for j,v in enumerate(b)),3-p) for i,x in enumerate(b) if x==0)
    seen={}
    def visit(b,p):
        if b in seen:return
        seen[b]=p
        if terminal(b,ws):return
        for i,v in enumerate(b):
            if not v:
                z=list(b);z[i]=p;visit(tuple(z),3-p)
    visit((0,)*9,1)
    rows=[]
    for b,p in seen.items():
        if terminal(b,ws):continue
        acts=[i for i,x in enumerate(b) if x==0];g=[];values=[]
        for i in acts:
            z=list(b);z[i]=p;z=tuple(z);ts=descendants(z,3-p)
            g.append(sum(winner(t,ws)==p for t in ts)/len(ts));values.append(-minimax(z,3-p))
        g=np.array(g);opt=np.array(values)==max(values);q=float(g.mean());ba=len(acts)
        pf=(g*(1+4*(1-q)**2)+(1-g)*(1-2*q)**2)/ba
        final=g/(ba*q) if q>0 else np.ones(ba)/ba
        maximizers=np.abs(g-g.max())<1e-12
        # Tie-safe definition: every maximal-probability action must be optimal.
        agreement=bool(np.all(opt[maximizers]))
        rows.append([float(opt.mean()),float(pf[opt].sum()),float(final[opt].sum()),float(q>0),float(agreement),float(np.any(opt[maximizers])),float(opt[maximizers].mean()),float(opt[int(np.argmax(g))])])
    arr=np.array(rows)
    checks=[]
    for root in (0,1,4):
        start=[0]*9;start[root]=1;expect=set(descendants(tuple(start),2));got=set()
        others=[i for i in range(9) if i!=root]
        for vals in product(range(3),repeat=8):
            d=sum(v!=0 for v in vals)
            if vals.count(1)!=d//2 or vals.count(2)!=(d+1)//2:continue
            b=start.copy()
            for i,v in zip(others,vals):b[i]=v
            if first_hit(b,ws,root,1 if d%2==0 else 2):got.add(tuple(b))
        assert got==expect
        checks.append(dict(root=root,terminals=len(got),set_equality=True))
    assert len(rows)==4520
    return dict(reachable_states=len(seen),nonterminal_states=len(rows),metrics=dict(zip(
        ['uniform_optimal_probability','filtered_optimal_probability','exact_final_optimal_probability','exact_final_marked_probability','all_maximizers_optimal_agreement','any_maximizer_optimal_agreement','uniform_tie_agreement','smallest_index_tie_agreement'],arr.mean(axis=0))),
        zero_win_states=int(len(rows)-arr[:,3].sum()),predicate_checks=checks)

def calibrate_gomoku(N=20000,seed=20260925,eta=.01):
    rng=random.Random(seed);ws=np.array(lines(7,5))
    wm=np.array([sum(1<<int(i) for i in w) for w in ws],dtype=np.uint64);mask=np.uint64((1<<49)-1)
    Md=[math.comb(48,(d+1)//2)*math.comb(48-(d+1)//2,d//2) for d in range(49)]
    M=sum(Md);cumulative=[];running=0
    for count in Md:running+=count;cumulative.append(running)
    a=1.;betas=[]
    for d in range(1,49):
        b=a/math.sqrt(49-d);betas.append(b);a=b*math.sqrt((d+1)//2)
    gamma=min(betas);scale=gamma*gamma*M;t=math.sqrt(math.log(10/eta)/(2*N));rows=[]
    for r in range(4):
        for c in range(r,4):
            root=7*r+c;others=np.array([i for i in range(49) if i!=root]);hits=0
            for start in range(0,N,2000):
                n=min(2000,N-start)
                ds=np.array([bisect.bisect_right(cumulative,rng.randrange(M)) for _ in range(n)])
                order=np.array([rng.sample(range(48),48) for _ in range(n)])
                vals=np.where(np.arange(48)[None,:]<ds[:,None]//2,1,np.where(np.arange(48)[None,:]<ds[:,None],2,0)).astype(np.uint8)
                board=np.zeros((n,49),dtype=np.uint8);board[:,root]=1
                board[np.arange(n)[:,None],others[order]]=vals
                lv=board[:,ws];wx=np.all(lv==1,axis=2);wo=np.all(lv==2,axis=2)
                hx=wx.any(axis=1);ho=wo.any(axis=1)
                ix=np.bitwise_and.reduce(np.where(wx,wm,mask),axis=1)&(mask^np.uint64(1<<root))
                io=np.bitwise_and.reduce(np.where(wo,wm,mask),axis=1)
                ok=((ds%2==0)&hx&~ho&(ix!=0))|((ds%2==1)&ho&~hx&(io!=0))|((ds==48)&~hx&~ho)
                hits+=int(ok.sum())
            rho=hits/N
            rows.append(dict(root=[r,c],samples=N,hits=hits,rho=rho,p_est=scale*rho,p_lower=scale*max(0,rho-t)))
    lb=min(x['p_lower'] for x in rows)
    s=schedule(lb,.001)
    return dict(seed=seed,sampler='integer-weight depth selection and unbiased discrete permutation; Python random.Random',eta=eta,total_samples=10*N,candidate_count=str(M),gamma=gamma,
                gamma_squared=gamma*gamma,gamma_squared_M=scale,hoeffding_radius=t,rows=rows,
                common_lower=lb,schedule=s,schedule_validation=validate_schedule(s))

def main():
    (ROOT/'results').mkdir(exist_ok=True)
    ttt=analyze_ttt();cal=calibrate_gomoku()
    for name,obj in [('ttt_exact.json',ttt),('gomoku_calibration.json',cal)]:
        (ROOT/'results'/name).write_text(json.dumps(obj,indent=2)+'\n')
    print(json.dumps({'ttt':ttt,'calibration':{k:v for k,v in cal.items() if k not in ('rows','schedule')},'K':cal['schedule']['K']},indent=2))

if __name__=='__main__':main()
