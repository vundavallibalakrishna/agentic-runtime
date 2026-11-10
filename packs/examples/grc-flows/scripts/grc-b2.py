exec(open('/tmp/grc-cli.py').read())
import time

A="qwenfresh"; e=json.load(open("/tmp/grc-proof/a.json")); d=e["docs"]
v=d["vendor-dpa-draft.md"]
t=time.time()
r=c.post(f"/api/v1/library-documents/{v}:rewrite",json={"anchor":"p1-s3","instruction":"Rewrite this security clause in precise contract language so the obligation is unambiguous, keeping its meaning.","modelAlias":A})
rw=r.json(); print(r.status_code, rw.get("status"), rw.get("proposed"), rw.get("hunks")); e["rewrite2_s"]=round(time.time()-t,1)
e["rewrite2_before"]=rw
print(json.dumps(c.get(f"/api/v1/library-documents/{v}/passages?pageFrom=1&pageTo=1").json())[:600])
r=c.post(f"/api/v1/document-rewrites/{rw['id']}:decide",json={"decision":"accept"})
print(r.status_code,r.text[:900]); e["rewrite2_after"]=r.json()
json.dump(e,open("/tmp/grc-proof/a.json","w"),indent=1)
