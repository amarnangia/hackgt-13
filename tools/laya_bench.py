# Benchmark Laya on sample call sentences.
# Usage: python tools/laya_bench.py mps [multilingual]   (or cpu)
import time, sys, torch, laya
dev = sys.argv[1]; sub = sys.argv[2] if len(sys.argv) > 2 else None
t=time.time(); a = laya.load("convaiinnovations/laya", device=dev, subfolder=sub); print(f"load {time.time()-t:.1f}s dev={dev} sub={sub}")
Q = {
 "visual": {"type":"noul","instructions":"Does the speaker mention a specific physical object, food, place or vehicle that a picture would help explain?"},
 "category": {"type":"choice","instructions":"What kind of thing is mentioned?","criteria":{
   "food":"a dish, snack, sweet or drink","vehicle":"rickshaw, scooter, bus, train","place":"temple, market, city, village","clothing":"saree, kurta, dupatta","festival":"Diwali, Holi, puja, wedding","none":"nothing concrete"}},
 "idiom": {"type":"noul","instructions":"Does the English sentence use slang or a figure of speech whose meaning is not literal?"},
}
cases = [
 ("Hindi","आज मैंने तुम्हारे लिए गाजर का हलवा बनाया","Today I made gajar ka halwa for you"),
 ("Hindi","मैं रिक्शा से मंदिर गई थी","I went to the temple by rickshaw"),
 ("Hindi","तुम्हारी पढ़ाई कैसी चल रही है?","How are your studies going?"),
 ("English","That concert was fire, no cap","That concert was fire, no cap"),
 ("English","I have an exam tomorrow","I have an exam tomorrow"),
 ("English","I'm so dead, I bombed that test","I'm so dead, I bombed that test"),
]
for lang, orig, en in cases:
    st = {"original": orig, "english": en}
    a.predict(st, Q)  # warm
    t=time.time(); N=5
    for _ in range(N): r = a.predict(st, Q)
    ms=(time.time()-t)/N*1000
    ans = r.get("answers", r)
    def g(k):
        v = ans[k]; 
        return v if not isinstance(v, dict) else {kk:(round(vv,2) if isinstance(vv,float) else vv) for kk,vv in v.items() if kk in ("answer","value","noul","choice","p_true","confidence")}
    print(f"{ms:6.1f}ms | {en[:38]:38} | visual={g('visual')} cat={g('category')} idiom={g('idiom')}")
