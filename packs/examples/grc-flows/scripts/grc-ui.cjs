const fs=require("node:fs"),path=require("node:path");
const {chromium}=require("/Users/balakrishnavundavalli/working/talentfino/cura/agentic_runtime/node_modules/.pnpm/playwright@1.64.1/node_modules/playwright");
const W="http://127.0.0.1:18132", OUT="/Users/balakrishnavundavalli/working/talentfino/cura/agentic_runtime/docs/testing/grc-flows";
const e=JSON.parse(fs.readFileSync("/tmp/grc-proof/a.json"));
const log=[];
async function settle(p){await p.waitForLoadState("networkidle").catch(()=>{});await p.waitForTimeout(2500);}
async function shot(p,n,full=true){const f=path.join(OUT,n+".png");await p.screenshot({path:f,fullPage:full});log.push(n);console.log("wrote",n);}
async function login(p,email="admin@dev.local"){await p.context().clearCookies();await p.goto(W+"/login");await p.getByRole("button",{name:`Sign in as ${email}`}).click();await p.waitForURL(/\/chat/,{timeout:20000});await settle(p);}
async function go(p,u){await p.goto(W+u);await settle(p);}
(async()=>{
 const b=await chromium.launch({headless:true});
 for (const theme of ["light","dark"]) {
  const ctx=await b.newContext({viewport:{width:1440,height:900},colorScheme:theme});
  await ctx.addInitScript(c=>localStorage.setItem("ar-theme",c),theme);
  const p=await ctx.newPage(); await login(p);
  const s=theme==="dark"?"-dark":"";
  await go(p,"/documents"); await shot(p,"a-documents-library"+s,false);
  await go(p,"/chat?conversation="+e.flowA.conversationId); await shot(p,"a-gap-result"+s);
  if(theme==="light"){ await go(p,"/documents/checks/"+e.check.id); await shot(p,"a-check-endpoint-lexical"); }
  await go(p,"/documents/compare?comparisonId="+e.compare.id); await shot(p,"b-policy-diff"+s);
  await go(p,"/documents/compare?comparisonId="+e.dpa_compare.id); await shot(p,"c-dpa-compare"+s);
  await go(p,"/chat?conversation="+e.flowC.conversationId); await shot(p,"c-dpa-redline"+s);
  if(theme==="light"){
   await go(p,"/documents/rewrites/"+e.rewrite3.id); await shot(p,"c-rewrite-proposed");
   const btn=p.getByRole("button",{name:/^accept/i}).first();
   if(await btn.count()){await btn.click();await settle(p);await shot(p,"c-rewrite-accepted");} else console.log("no accept button");
   await go(p,"/documents/rewrites/"+e.rewrite2_after.id); await shot(p,"c-rewrite-accepted-api");
  }
  await go(p,"/knowledge/"+e.collection); await shot(p,"d-knowledge-collection"+s);
  await go(p,"/chat?conversation="+e.flowD.conversationId); await shot(p,"d-questionnaire-cited"+s);
  await go(p,"/agents/"+e.flowE.agentId);
  const tab=p.getByRole("tab",{name:/expose/i}); if(await tab.count()){await tab.first().click();await settle(p);} else console.log("no expose tab");
  const txt=await p.locator("body").innerText(); if(/ar_[a-z]*_[A-Za-z0-9]{20,}/.test(txt)) console.log("WARN possible key on page");
  await shot(p,"e-expose-mcp"+s);
  await go(p,"/agents"); await shot(p,"grc-agents"+s,false);
  if(theme==="light"){ await go(p,"/approvals"); await shot(p,"f-approval"); await go(p,"/inbox"); await shot(p,"f-inbox"); }
  await ctx.close();
 }
 await b.close(); fs.writeFileSync("/tmp/grc-proof/ui.json",JSON.stringify(log));
})().catch(x=>{console.error(x);process.exit(1)});
