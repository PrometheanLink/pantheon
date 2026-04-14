// Pygmalion — Headless browser probe for UI debugging.
//
// Drives real Chrome against your deployed site, captures JS errors,
// network failures, and screenshots. Use this FIRST when debugging
// frontend bugs you can't reproduce from logs alone.
//
// USAGE:
//   PANTHEON_TOKEN=<your-jwt> \
//   PANTHEON_URL=https://yoursite.com/dashboard \
//   node scripts/pygmalion/probe.mjs
//
// OPTIONAL ENV VARS:
//   PANTHEON_CLICK_SELECTOR  — CSS selector to click after first navigation
//                              (e.g. 'a[href*="/dashboard/jobs/"]:first-of-type')
//   PANTHEON_OUTPUT_DIR      — where to write screenshots (default /tmp/pygmalion)
//   PANTHEON_VIEWPORT        — "WxH" (default "1400x900")
//   PANTHEON_WAIT_MS         — extra ms to wait after navigation (default 2000)
//   PANTHEON_TIMEOUT_MS      — navigation timeout (default 30000)
//
// OUTPUT:
//   - All console messages (typed: log/warn/error)
//   - All page errors (uncaught JS) with full Chrome stack traces
//   - All failed network requests
//   - Screenshot at $PANTHEON_OUTPUT_DIR/probe-<timestamp>.png
//
// EXIT CODE:
//   0 = no page errors (clean)
//   1 = page errors found
//   2 = missing required env vars
//
// PREREQUISITES:
//   npm install playwright
//   npx playwright install chromium
//
// WHY THIS EXISTS:
//   curl tells you the HTTP status. Playwright tells you what the USER sees.
//   When a user reports "the page is broken" but your API returns 200,
//   the bug lives in JavaScript — and only a real browser can catch it.
//   Pygmalion gives Claude Code browser eyes.

import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const TOKEN = process.env.PANTHEON_TOKEN;
const TARGET_URL = process.env.PANTHEON_URL;
const CLICK = process.env.PANTHEON_CLICK_SELECTOR;
const OUT = process.env.PANTHEON_OUTPUT_DIR || '/tmp/pygmalion';
const [VW, VH] = (process.env.PANTHEON_VIEWPORT || '1400x900').split('x').map(Number);
const WAIT_MS = parseInt(process.env.PANTHEON_WAIT_MS || '2000', 10);
const TIMEOUT_MS = parseInt(process.env.PANTHEON_TIMEOUT_MS || '30000', 10);

if (!TOKEN || !TARGET_URL) {
  console.error('ERROR: PANTHEON_TOKEN and PANTHEON_URL are required');
  console.error('');
  console.error('Usage:');
  console.error('  PANTHEON_TOKEN=<jwt> PANTHEON_URL=https://yoursite.com/page node scripts/pygmalion/probe.mjs');
  console.error('');
  console.error('To mint a token, use your app\'s auth system to generate a JWT,');
  console.error('or see scripts/pygmalion/mint-token.sh for an example.');
  process.exit(2);
}

mkdirSync(OUT, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const screenshotPath = `${OUT}/probe-${stamp}.png`;

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: VW, height: VH } });
const page = await ctx.newPage();

// --- Collectors ---
const consoleLog = [];
const errors = [];
const networkFails = [];

page.on('console', msg => {
  const entry = { type: msg.type(), text: msg.text() };
  try {
    const loc = msg.location();
    if (loc?.url) entry.where = `${loc.url}:${loc.lineNumber}:${loc.columnNumber}`;
  } catch {}
  consoleLog.push(entry);
});

page.on('pageerror', err => {
  errors.push({
    name: err.name,
    message: err.message,
    stack: err.stack,
  });
});

page.on('requestfailed', req => {
  const f = req.failure();
  networkFails.push({ url: req.url(), error: f?.errorText || 'unknown' });
});

// --- Inject auth token into localStorage BEFORE any user JS runs ---
// Customize this for your auth mechanism. Most Next.js / React apps
// store the JWT in localStorage under a key like 'access_token' or 'token'.
await page.addInitScript(token => {
  try { localStorage.setItem('access_token', token); } catch {}
}, TOKEN);

console.log('==> probe target:', TARGET_URL);
console.log('==> viewport:', VW, 'x', VH);
console.log('==> mode:', CLICK ? 'navigate-then-click' : 'navigate-only');
console.log();

// --- Navigate ---
const t0 = Date.now();
const resp = await page.goto(TARGET_URL, {
  waitUntil: 'networkidle',
  timeout: TIMEOUT_MS,
}).catch(e => ({ err: e.message }));
console.log('==> initial nav:', resp?.status?.() ?? resp);
console.log('==> took:', Date.now() - t0, 'ms');

await page.waitForTimeout(WAIT_MS);

// --- Optional click-through ---
if (CLICK) {
  console.log('==> looking for click selector:', CLICK);
  const target = await page.$(CLICK);
  if (!target) {
    console.log('   no element matched');
  } else {
    const href = await target.getAttribute('href').catch(() => null);
    console.log('   matched, href =', href);
    const errsBefore = errors.length;
    if (href && href.startsWith('/')) {
      await page.goto(new URL(href, TARGET_URL).toString(), {
        waitUntil: 'networkidle',
        timeout: TIMEOUT_MS,
      }).catch(e => console.log('   nav err:', e.message));
    } else {
      await target.click({ timeout: TIMEOUT_MS }).catch(e => console.log('   click err:', e.message));
      await page.waitForLoadState('networkidle', { timeout: TIMEOUT_MS }).catch(() => {});
    }
    await page.waitForTimeout(WAIT_MS);
    console.log('==> after click — new errors:', errors.length - errsBefore);
  }
}

// --- Results ---
const finalUrl = page.url();
const title = await page.title().catch(() => '?');
console.log('==> final url:', finalUrl);
console.log('==> title:', title);

await page.screenshot({ path: screenshotPath, fullPage: true });
console.log('==> screenshot:', screenshotPath);

console.log();
console.log('=== CONSOLE LOG (' + consoleLog.length + ' entries) ===');
for (const c of consoleLog) {
  console.log(`[${c.type}]${c.where ? ' @' + c.where : ''} ${c.text}`);
}

console.log();
console.log('=== PAGE ERRORS (' + errors.length + ') ===');
if (errors.length === 0) {
  console.log('  (none)');
}
for (const e of errors) {
  console.log(`${e.name}: ${e.message}`);
  if (e.stack) {
    console.log(e.stack.split('\n').slice(0, 25).join('\n'));
  }
  console.log('---');
}

console.log();
console.log('=== NETWORK FAILURES (' + networkFails.length + ') ===');
if (networkFails.length === 0) {
  console.log('  (none)');
} else {
  for (const f of networkFails) {
    console.log(`  ${f.error}: ${f.url}`);
  }
}

await browser.close();

// Exit code: 0 = clean, 1 = page errors found
process.exit(errors.length > 0 ? 1 : 0);
