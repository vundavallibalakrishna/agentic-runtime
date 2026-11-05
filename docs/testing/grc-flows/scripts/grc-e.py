exec(open('/tmp/grc-cli.py').read())
import time
A="qwenfresh"; e=json.load(open("/tmp/grc-proof/a.json")); d=e["docs"]
slug="grc-control-checker"
ex=[a for a in (c.get("/api/v1/agents").json().get("items") or []) if a.get("slug")==slug]
if ex: aid=ex[0]["id"]
else:
    a=c.post("/api/v1/agents",json={"slug":slug,"name":"GRC Control Checker","visibility":"private","definition":{"instructions":f"You check compliance controls against ACME's information security policy. The current policy is library document {d['acme-information-security-policy-v2.md']}. Always call documents.read with only the documentId argument (never pass an anchor) to read the whole policy, then answer with: Control, Verdict (met / partial / not_found), Evidence (section number and exact quote), Gap. Never invent text.","model":{"alias":A},"tools":[{"server":"documents","version":"*","include":["read","list"]}],"budget":{"maxSteps":8,"maxToolCalls":4,"maxWallClockS":300,"maxCostMicros":10000000,"maxTokens":8000}}}).json()
    aid=a["id"]; print(c.post(f"/api/v1/agents/{aid}:publish",json={"changeNote":"GRC demo","skipEvalGate":True}).status_code)
k=c.post(f"/api/v1/agents/{aid}/api-keys",json={"label":"GRC demo embed","rateLimitRpm":30,"monthlyQuota":200}).json()
key=k["key"]; prefix=k.get("prefix") or key[:8]
x=httpx.Client(base_url=B,timeout=300,headers={"Authorization":f"Bearer {key}"})
def scrub(o): s=json.dumps(o); assert key not in s; return o
t=time.time()
lst=x.post("/v1/mcp",headers={"Accept":"application/json"},json={"jsonrpc":"2.0","id":1,"method":"tools/list"}).json()
call=x.post("/v1/mcp",headers={"Accept":"application/json"},json={"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"agent_grc_control_checker","arguments":{"message":"Check control CC6.1-MFA (Multi-factor authentication is enforced for all access to production systems) against the ACME policy."}}}).json()
mcp_s=round(time.time()-t,1); t=time.time()
cv=x.post(f"/v1/agents/{slug}/conversations").json()
rest=x.post(f"/v1/agents/{slug}/conversations/{cv['id']}/messages",json={"text":"Check control CC9.2 (Vendors are assessed for security risk before onboarding and re-assessed periodically) against the ACME policy."}).json()
rest_s=round(time.time()-t,1)
e["flowE"]=scrub({"agentId":aid,"slug":slug,"keyPrefix":prefix,"mcpToolsList":[i.get("name") for i in lst.get("result",{}).get("tools",[])],"mcpCall":call,"mcp_s":mcp_s,"restConversation":cv.get("id"),"rest":rest,"rest_s":rest_s})
json.dump(e,open("/tmp/grc-proof/a.json","w"),indent=1)
print(json.dumps(e["flowE"],indent=1)[:5000])
