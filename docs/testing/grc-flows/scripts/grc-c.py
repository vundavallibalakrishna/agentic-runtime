exec(open('/tmp/grc-cli.py').read())
import time,sys,pathlib
A="qwenfresh"; e=json.load(open("/tmp/grc-proof/a.json")); d=e["docs"]
F=pathlib.Path("docs/testing/grc-flows/fixtures")
def B(s=12,cl=10): return {"maxSteps":s,"maxToolCalls":cl,"maxWallClockS":400,"maxCostMicros":20000000,"maxTokens":12000}
def body(r):
    if r.status_code>=300: raise SystemExit(f"{r.request.method} {r.request.url} {r.status_code} {r.text[:800]}")
    return r.json()
def publish(slug,name,defn):
    ex=[a for a in (c.get("/api/v1/agents").json().get("items") or []) if a.get("slug")==slug]
    if ex: return ex[0]["id"]
    a=body(c.post("/api/v1/agents",json={"slug":slug,"name":name,"visibility":"private","definition":defn}))
    body(c.post(f"/api/v1/agents/{a['id']}:publish",json={"changeNote":"GRC demo","skipEvalGate":True})); return a["id"]
def wait(rid,sec=420):
    t=time.time()
    while time.time()-t<sec:
        cur=body(c.get(f"/api/v1/runs/{rid}"))
        if cur.get("status") not in ("queued","running"): break
        time.sleep(3)
    calls=c.get(f"/api/v1/runs/{rid}/tool-calls").json()
    return {"runId":rid,"status":cur.get("status"),"summary":cur.get("resultSummary"),"error":cur.get("error"),"seconds":round(time.time()-t,1),"tools":[x.get("toolName") or x.get("qualifiedName") or x.get("name") for x in (calls.get("items") or [])]}
def chat(aid,text):
    cv=body(c.post("/api/v1/conversations",json={"agentId":aid,"modelAlias":A}))
    p=body(c.post(f"/api/v1/conversations/{cv['id']}/messages",json={"text":text}))
    r=wait(p["run"]["id"]); r["conversationId"]=cv["id"]; return r
DOC={"server":"documents","version":"*","include":["list","read","outline","check","compare","search","rewrite","gaps"]}
which=sys.argv[1]
if which=="A":
    aid=publish("grc-policy-gap-analyst","GRC Policy Gap Analyst",{"instructions":"You are a GRC gap analyst. Use the documents tools to read the policy and the control list from the document library. For every control return a markdown table with columns Control | Verdict (met, partial, not_found) | Evidence (section number and a short exact quote) | Gap. Base verdicts only on the policy text; if the policy says nothing, the verdict is not_found. Never invent sections.","model":{"alias":A},"tools":[{"server":"documents","version":"*","include":["read","outline"]}],"budget":B()})
    p1=d["acme-information-security-policy-v1.md"]; cs=d["soc2-cc-subset.csv"]
    r=chat(aid,f"Run a gap analysis of the ACME Information Security Policy v1 (document {p1}) against the SOC 2 / ISO control list (document {cs}). Read both documents in full with documents.read, judge each control yourself against the policy wording, then give the full table for all 12 controls and a one-line overall summary.")
    e["flowA_agent"]=aid; e["flowA"]=r
if which=="C":
    aid=publish("grc-dpa-reviewer","GRC DPA Reviewer",{"instructions":"You are a privacy counsel assistant. Compare a vendor DPA against the customer's standard DPA using the documents tools (compare and read). Report a table Clause | Status (missing, weakened, added, same) | Standard says | Vendor says | Risk. Then propose redline text for each missing or weakened clause, citing the standard clause number. Flag GDPR Article 28 gaps explicitly.","model":{"alias":A},"tools":[DOC],"budget":B()})
    r=chat(aid,f"Review the CloudNimbus vendor DPA (document {d['vendor-dpa-draft.md']}) against the ACME standard DPA (document {d['acme-dpa-standard.md']}). Give the clause table, list Article 28 gaps, and propose redlines.")
    e["flowC_agent"]=aid; e["flowC"]=r
if which=="D":
    if "collection" not in e:
        col=body(c.post("/api/v1/knowledge/collections",json={"name":"ACME Trust Library","slug":"acme-trust-library","description":"Security policy v2 and SOC 2 excerpt used to answer vendor questionnaires","embeddingAlias":"bge-m3"}))
        for k in ["acme-information-security-policy-v2.md","acme-soc2-report-excerpt.md"]:
            body(c.post(f"/api/v1/knowledge/collections/{col['id']}/members",json={"kind":"library","libraryDocumentId":d[k]}))
        e["collection"]=col["id"]; time.sleep(15)
    aid=publish("grc-questionnaire-responder","GRC Questionnaire Responder",{"instructions":"You answer customer security questionnaires for ACME using only the ACME Trust Library knowledge passages. For each question give: id, answer, and a citation like [1] that points to the passage. If the passages do not support an answer, write 'Not supported by our documents - needs owner input' and do not guess.","model":{"alias":A},"knowledge":{"collections":["acme-trust-library"]},"tools":[{"server":"knowledge","version":"*","include":["search"]}],"budget":B()})
    qs=(F/"vendor-questionnaire.csv").read_text()
    r=chat(aid,"Answer this vendor security questionnaire for ACME. Search the trust library for each question.\n\n"+qs)
    e["flowD_agent"]=aid; e["flowD"]=r
json.dump(e,open("/tmp/grc-proof/a.json","w"),indent=1)
print(json.dumps({k:v for k,v in e.items() if k.startswith("flow")},indent=1)[:6000])
