exec(open('/tmp/grc-cli.py').read())
import time

A="qwenfresh"; e=json.load(open("/tmp/grc-proof/a.json")); d=e["docs"]
v=d["vendor-dpa-draft.md"]
t=time.time()
r=c.post(f"/api/v1/library-documents/{v}:rewrite",json={"anchor":"p1-s4","instruction":"Redline this sub-processor clause to match ACME's standard: the Processor shall not engage a sub-processor without at least 30 days' prior written notice to the Controller, the Controller may object, and the Processor remains liable for its sub-processors.","modelAlias":A})
print(r.status_code,r.text[:1500]); rw=r.json(); e["rewrite_s"]=round(time.time()-t,1)
e["rewrite_before"]=c.get(f"/api/v1/document-rewrites/{rw['id']}").json()
r=c.post(f"/api/v1/document-rewrites/{rw['id']}:decide",json={"decision":"accept"})
print(r.status_code,r.text[:1500]); e["rewrite_after"]=r.json()
json.dump(e,open("/tmp/grc-proof/a.json","w"),indent=1)
