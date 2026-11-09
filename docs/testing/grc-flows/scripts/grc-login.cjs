// Capture a Keycloak OIDC session for the GRC proof.
// dev-login was removed on HEAD (M38b-T05b: the IdP is the only way in), so sign in through the
// real browser flow and write the ar_session/ar_csrf cookies to /tmp/grc-cookies.json for
// grc_proof.py to reuse. Uses the Playwright that ships in apps/web.
const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../../../../apps/web/node_modules/@playwright/test'));

(async () => {
  const email = process.env.EMAIL || 'admin@dev.local';
  const pw = process.env.PW || 'dev-password';
  const base = process.env.BASE || 'http://127.0.0.1:3000';
  const out = process.env.OUT || '/tmp/grc-cookies.json';
  const b = await chromium.launch();
  const ctx = await b.newContext();
  const p = await ctx.newPage();
  await p.goto(base + '/api/v1/auth/login', { waitUntil: 'domcontentloaded' });
  for (let step = 0; step < 3 && !p.url().startsWith(base); step++) {
    if (await p.$('#username')) await p.fill('#username', email);
    if (await p.$('#password')) await p.fill('#password', pw);
    await Promise.all([
      p.waitForLoadState('networkidle').catch(() => {}),
      p.click('#kc-login, [name=login], button[type=submit]').catch(() => {}),
    ]);
  }
  await p.waitForURL(u => u.toString().startsWith(base), { timeout: 15000 }).catch(() => {});
  const want = {};
  for (const c of await ctx.cookies()) if (c.name === 'ar_session' || c.name === 'ar_csrf') want[c.name] = c.value;
  require('fs').writeFileSync(out, JSON.stringify(want));
  console.log('final url:', p.url().slice(0, 60), '| cookies:', Object.keys(want).join(',') || 'NONE');
  await b.close();
  process.exit(Object.keys(want).length ? 0 : 1);
})().catch(e => { console.error('login error:', e.message); process.exit(2); });
