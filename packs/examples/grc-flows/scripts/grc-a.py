exec(open('/tmp/grc-cli.py').read())
import csv
import pathlib
import time

F=pathlib.Path("docs/testing/grc-flows/fixtures")
A="qwenfresh"; ev={}
def up(n,mime="text/markdown"):
    r=c.post("/api/v1/library-documents",files={"upload":(n,(F/n).read_bytes(),mime)}); r.raise_for_status(); return r.json()
docs={n:up(n) for n in ["acme-information-security-policy-v1.md","acme-information-security-policy-v2.md","acme-dpa-standard.md","vendor-dpa-draft.md","acme-soc2-report-excerpt.md"]}
docs["soc2-cc-subset.csv"]=up("soc2-cc-subset.csv","text/csv")
ev["docs"]={k:v["id"] for k,v in docs.items()}
reqs=[f'{r["control_id"]}: {r["statement"]}' for r in csv.DictReader(open(F/"soc2-cc-subset.csv"))]
t=time.time()
r=c.post(f'/api/v1/library-documents/{docs["acme-information-security-policy-v1.md"]["id"]}:check',json={"requirements":reqs,"label":"SOC 2 / ISO subset vs ACME policy v1","modelAlias":A})
print("check",r.status_code,round(time.time()-t,1)); ev["check"]=r.json(); ev["check_s"]=round(time.time()-t,1)
t=time.time()
r=c.post(f'/api/v1/library-documents/{docs["acme-information-security-policy-v1.md"]["id"]}:compare',json={"otherDocumentId":docs["acme-information-security-policy-v2.md"]["id"],"modelAlias":A})
print("cmp",r.status_code,round(time.time()-t,1)); ev["compare"]=r.json(); ev["compare_s"]=round(time.time()-t,1)
t=time.time()
r=c.post(f'/api/v1/library-documents/{docs["acme-dpa-standard.md"]["id"]}:compare',json={"otherDocumentId":docs["vendor-dpa-draft.md"]["id"],"modelAlias":A})
print("dpa",r.status_code,round(time.time()-t,1)); ev["dpa_compare"]=r.json(); ev["dpa_compare_s"]=round(time.time()-t,1)
json.dump(ev,open("/tmp/grc-proof/a.json","w"),indent=1)
