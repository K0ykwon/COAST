"""Report raw probabilities including invalid codes; no silent postselection."""
import argparse,json
import numpy as np
from scipy.stats import beta
from coast_analysis import ROOT,winner,lines

def ci(k,n,alpha=.05):
    return [0. if k==0 else float(beta.ppf(alpha/2,k,n-k+1)),1. if k==n else float(beta.ppf(1-alpha/2,k+1,n-k))]

def main():
    p=argparse.ArgumentParser();p.add_argument('runtime_json');a=p.parse_args()
    r=json.load(open(a.runtime_json));f=json.loads((ROOT/'results'/f"{r['fixture']}_fixture.json").read_text())
    counts=r['counts'];N=sum(counts.values());nact=len(f['actions']);root_counts=np.zeros(nact+1);invalid=marked=opt=0
    b=f['action_qubits'];ts=f['terminal_boards'];ws=lines(f['board_size'],f['win_length'])
    for bitstring,count in counts.items():
        code=int(bitstring.replace(' ',''),2);action=code&((1<<b)-1);terminal_id=code>>b
        bad=action>=nact or terminal_id>=len(ts)
        # Valid individually indexed values can still form an unreachable (action, terminal) pair.
        if not bad:bad=terminal_id not in f['terminal_ids_by_action'][action]
        if bad:invalid+=count;root_counts[-1]+=count;continue
        root_counts[action]+=count
        if winner(ts[terminal_id],ws)==f['player']:marked+=count
        if action in f['optimal_action_codes']:opt+=count
    stage=r['stage']
    expected=np.array(([1/nact]*nact if stage=='prepare' else f['filtered_action_probabilities'] if stage=='filter' else f['final_action_probabilities'])+[0])
    observed=root_counts/N
    print(json.dumps(dict(shots=N,raw_root_distribution_with_invalid_bin=observed.tolist(),invalid_probability=invalid/N,
        invalid_95ci=ci(invalid,N),marked_probability=marked/N,marked_95ci=ci(marked,N),optimal_action_probability=opt/N,
        optimal_95ci=ci(opt,N),root_total_variation=float(abs(observed-expected).sum()/2),postselection=False),indent=2))

if __name__=='__main__':main()
