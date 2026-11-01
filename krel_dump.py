import sys, struct
data = open(sys.argv[1], 'rb').read()
pos = 0
def rd8():
    global pos; v = data[pos]; pos += 1; return v
def ruleb():
    global pos; v = 0; sh = 0
    while True:
        x = rd8(); v |= (x & 0x7f) << sh
        if not (x & 0x80): break
        sh += 7
    return v
def rsleb():
    global pos; v = 0; sh = 0
    while True:
        x = rd8(); v |= (x & 0x7f) << sh; sh += 7
        if not (x & 0x80): break
    if sh < 64 and (x & 0x40): v |= (~0 << sh) & ((1<<64)-1)
    return v - (1<<64) if v >= (1<<63) else v
def rtype():
    k = rd8()
    if k in (1, 2): return (k, rd8())
    if k == 4: return (k, rd8(), rd8(), rd8())
    return (k,)
def rname():
    n = ruleb(); global pos
    s = data[pos:pos+n].decode(); pos += n; return s
def rval(): return ruleb() - 1
assert data[:4] == b'KREL'
pos = 4
ver = rd8() | (rd8() << 8)
print("version", ver)
OPS = {1:'iconst',2:'fconst',3:'freeze',4:'add',5:'sub',6:'mul',7:'udiv',8:'sdiv',9:'urem',10:'srem',11:'neg',12:'and',13:'or',14:'xor',15:'not',16:'shl',17:'lshr',18:'ashr',19:'icmp',20:'popcount',21:'clz',22:'ctz',23:'bswap',24:'trunc',25:'zext',26:'sext',27:'fadd',28:'fsub',29:'fmul',30:'fdiv',31:'fneg',32:'fabs',33:'fma',34:'fcmp',35:'ftrunc',36:'fext',37:'fptosi',38:'fptoui',39:'sitofp',40:'uitofp',41:'bitcast',42:'alloca',43:'load',44:'store',45:'gep',46:'memcpy',47:'memset',48:'dataptr',49:'vsplat',65:'aload',66:'astore',67:'aadd',68:'br',69:'condbr',70:'ret',71:'call',72:'tailcall',73:'select',74:'assume'}
tot = dict(nfuncs=0, nblocks=0, nins=0, pool=0, nexts=0, ndata=0, blob=0, mainidx=-1, totvals=0)
while pos < len(data):
    sid = rd8(); slen = ruleb(); send = pos + slen
    if sid == 2:
        n = ruleb(); tot['nexts'] = n
        for i in range(n):
            nm = rname(); np = ruleb()
            ps = [rtype() for _ in range(np)]; rt = rtype()
            print(f"extern {nm} np={np} ret={rt}")
    elif sid == 3:
        n = ruleb(); tot['ndata'] = n
        for i in range(n):
            nm = rname(); al = ruleb(); ln = ruleb()
            print(f"data {nm} align={al} len={ln} bytes={data[pos:pos+min(ln,24)]!r}")
            pos += ln; tot['blob'] += (ln + 15) & ~15
    elif sid == 4:
        n = ruleb(); tot['nfuncs'] = n
        for fi in range(n):
            nm = rname(); fl = rd8(); rt = rtype(); nb = ruleb()
            if nm == 'main': tot['mainidx'] = fi
            mx = -1
            print(f"func {fi} {nm} flags={fl} ret={rt} blocks={nb}")
            for bi in range(nb):
                na = ruleb(); args = []
                for k in range(na):
                    avid = ruleb(); at = rtype(); args.append((avid, at)); mx = max(mx, avid); tot['pool'] += 1
                ni = ruleb(); tot['nblocks'] += 1; tot['nins'] += ni
                print(f"  block {bi} args={args} nins={ni}")
                for ii in range(ni):
                    op = rd8(); res = rval(); ty = rtype()
                    mx = max(mx, res)
                    extra = ''
                    if op == 1: extra = f" imm={rsleb()}"
                    elif op == 2: extra = f" imm={ruleb()}"
                    elif op == 68:
                        blk = ruleb(); na2 = ruleb(); aa = [rval() for _ in range(na2)]; tot['pool'] += na2
                        extra = f" blk={blk} args={aa}"
                    elif op == 69:
                        a = rval(); blk = ruleb(); na2 = ruleb(); aa = [rval() for _ in range(na2)]
                        blk2 = ruleb(); nb2 = ruleb(); ab = [rval() for _ in range(nb2)]
                        tot['pool'] += na2 + nb2
                        extra = f" a={a} blk={blk} args={aa} blk2={blk2} args2={ab}"
                    elif op in (71, 72):
                        ce = ruleb(); cx = rd8(); na2 = ruleb(); aa = [rval() for _ in range(na2)]; tot['pool'] += na2
                        extra = f" callee={ce} extern={cx} args={aa}"
                    elif op == 70: extra = f" a={rval()}"
                    elif op in (19, 34):
                        pr = rd8(); extra = f" pred={pr} a={rval()} b={rval()}"
                    elif op == 42: extra = f" imm={ruleb()} c={ruleb()}"
                    elif op == 48: extra = f" imm={ruleb()}"
                    elif op == 45: extra = f" a={rval()} b={rval()} ety={rtype()}"
                    elif op in (63,): extra = f" a={rval()} imm={ruleb()}"
                    elif op in (64,): extra = f" a={rval()} b={rval()} imm={ruleb()}"
                    elif op in (65, 66, 67):
                        aux = rd8(); a = rval(); extra = f" aux={aux} a={a}" + (f" b={rval()}" if op != 65 else "")
                    else: extra = f" a={rval()} b={rval()} c={rval()}"
                    print(f"    {ii}: {OPS.get(op, op)} -> {res} ty={ty}{extra}")
            tot['totvals'] += mx + 1
    pos = send
print("TOTALS", tot)
