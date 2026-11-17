import itertools, random, statistics
N=6
ROWS=[r for r in itertools.product([0,1],repeat=N) if sum(r)==3 and all(not(r[i]==r[i+1]==r[i+2]) for i in range(N-2))]
def grids():
    out=[]
    def ok(g):
        for c in range(N):
            col=[g[r][c] for r in range(len(g))]
            if sum(col)>3 or len(g)-sum(col)>3: return False
            if len(col)>=3 and col[-1]==col[-2]==col[-3]: return False
        return True
    def rec(g):
        if len(g)==N: out.append(tuple(g));return
        for r in ROWS:
            g.append(r)
            if ok(g): rec(g)
            g.pop()
    rec([]);return out
ALL=grids()
# clue model: givens {(r,c):v}, links {((r,c),(r2,c2)):'='/'x'}
def consistent(g,givens,links):
    return all(g[r][c]==v for (r,c),v in givens.items()) and all((g[a[0]][a[1]]==g[b[0]][b[1]])==(t=='=') for (a,b),t in links.items())
def count(givens,links,cap=2):
    n=0
    for g in ALL:
        if consistent(g,givens,links):
            n+=1
            if n>=cap:break
    return n
# logic-only solver (no guessing): propagate local rules to fixpoint
def propagate(givens,links):
    b=[[None]*N for _ in range(N)]
    for (r,c),v in givens.items(): b[r][c]=v
    steps=set()
    def setv(r,c,v,rule):
        if b[r][c] is None: b[r][c]=v; steps.add(rule); return True
        return False
    ch=True
    while ch:
        ch=False
        for (a,bb),t in links.items():
            for x,y in((a,bb),(bb,a)):
                if b[x[0]][x[1]] is not None and b[y[0]][y[1]] is None:
                    v=b[x[0]][x[1]]; ch|=setv(*y,v if t=='=' else 1-v,'link')
        lines=[[(r,c) for c in range(N)] for r in range(N)]+[[(r,c) for r in range(N)] for c in range(N)]
        for L in lines:
            vals=[b[r][c] for r,c in L]
            for v in(0,1):
                if vals.count(v)==3:
                    for (r,c) in L:
                        if b[r][c] is None: ch|=setv(r,c,1-v,'count')
            for i in range(N-2):
                t=vals[i:i+3]
                if t[0]==t[1]!=None and t[2] is None: ch|=setv(*L[i+2],1-t[0],'pair')
                if t[1]==t[2]!=None and t[0] is None: ch|=setv(*L[i],1-t[1],'pair')
                if t[0]==t[2]!=None and t[1] is None: ch|=setv(*L[i+1],1-t[0],'gap')
            vals=[b[r][c] for r,c in L]
    return b,steps
def solved(b): return all(x is not None for row in b for x in row)
def make(seed,target_logic=True):
    rnd=random.Random(seed); sol=rnd.choice(ALL)
    cells=[(r,c) for r in range(N) for c in range(N)]
    givens={p:sol[p[0]][p[1]] for p in cells}
    links={}
    for r in range(N):
        for c in range(N):
            for dr,dc in((0,1),(1,0)):
                r2,c2=r+dr,c+dc
                if r2<N and c2<N: links[((r,c),(r2,c2))]='=' if sol[r][c]==sol[r2][c2] else 'x'
    # remove clues in random order while solution stays unique AND logic-solvable
    items=[('g',k) for k in givens]+[('l',k) for k in links]; rnd.shuffle(items)
    for kind,k in items:
        g2=dict(givens);l2=dict(links)
        (g2 if kind=='g' else l2).pop(k)
        if count(g2,l2)==1 and solved(propagate(g2,l2)[0]):
            givens,links=g2,l2
    return sol,givens,links
if __name__=='__main__':
    res=[]
    for s in range(40):
        sol,g,l=make(s)
        b,steps=propagate(g,l)
        res.append((len(g),len(l),len(g)+len(l),tuple(sorted(steps))))
    print("puzzles:",len(res))
    print("givens  mean/min/max:",statistics.mean(x[0] for x in res),min(x[0] for x in res),max(x[0] for x in res))
    print("links   mean/min/max:",statistics.mean(x[1] for x in res),min(x[1] for x in res),max(x[1] for x in res))
    print("total   mean/min/max:",statistics.mean(x[2] for x in res),min(x[2] for x in res),max(x[2] for x in res))
    from collections import Counter
    print(Counter(x[3] for x in res))
    # example
    sol,g,l=make(7)
    print("example givens:",sorted(g.items()))
    print("example links:",sorted(l.items()))
