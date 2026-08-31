import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'https://helm-company-cockpit.vercel.app';
const SCREENSHOT_DIR = '/workspace/helm-debug/screenshots';
const RESULTS_FILE = '/workspace/helm-debug/results-detailed.json';

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const results = {
  timestamp: new Date().toISOString(),
  allNetworkRequests: [],
  apiCalls: [],
  clerkCalls: [],
  failedRequests: [],
  consoleErrors: [],
  consoleWarnings: [],
  consoleLogs: [],
};

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  // Capture ALL network
  page.on('response', async (response) => {
    const url = response.url();
    const status = response.status();
    let body = '';
    try {
      const ct = response.headers()['content-type'] || '';
      if ((ct.includes('json') || ct.includes('text')) && !url.includes('.js') && !url.includes('.css') && !url.includes('.woff')) {
        body = await response.text();
      }
    } catch {}

    const entry = {
      url,
      status,
      method: response.request().method(),
      body: body.slice(0, 3000),
      time: new Date().toISOString(),
    };

    results.allNetworkRequests.push(entry);

    if (url.includes('/api/')) {
      results.apiCalls.push(entry);
      if (status >= 400) results.failedRequests.push(entry);
    }
    if (url.includes('clerk') || url.includes('clerk.com') || url.includes('accounts.dev')) {
      results.clerkCalls.push(entry);
      if (status >= 400) results.failedRequests.push(entry);
    }
    if (status >= 400 && !url.includes('.js') && !url.includes('.css') && !url.includes('.png') && !url.includes('.woff') && !url.includes('.svg')) {
      if (!results.failedRequests.find(r => r.url === url && r.status === status)) {
        results.failedRequests.push(entry);
      }
    }
  });

  page.on('console', (msg) => {
    const entry = { type: msg.type(), text: msg.text(), time: new Date().toISOString() };
    if (msg.type() === 'error') results.consoleErrors.push(entry);
    else if (msg.type() === 'warning') results.consoleWarnings.push(entry);
    else if (msg.type() === 'log' && (msg.text().includes('auth') || msg.text().includes('clerk') || msg.text().includes('error'))) {
      results.consoleLogs.push(entry);
    }
  });

  page.on('pageerror', (error) => {
    results.consoleErrors.push({ type: 'pageerror', text: error.message, stack: error.stack });
  });

  // Listen for popups (Google OAuth)
  const popups = [];
  page.on('popup', async (popup) => {
    popups.push({ url: popup.url(), time: new Date().toISOString() });
    results.popups = popups;
  });

  try {
    // === SIGN-UP with full email flow ===
    console.log('=== SIGN-UP EMAIL FLOW ===');
    await page.goto(`${BASE_URL}/sign-up`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '10-signup-initial.png'), fullPage: true });

    // Dismiss cookie banner if present
    const cookieBtn = page.locator('button:has-text("Got it")');
    if (await cookieBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cookieBtn.click();
      await page.waitForTimeout(500);
    }

    // Fill sign-up form
    const emailInput = page.locator('input[name="emailAddress"], input[type="email"]').first();
    const passwordInput = page.locator('input[name="password"], input[type="password"]').first();
    const firstNameInput = page.locator('input[name="firstName"]').first();
    const continueBtn = page.locator('.cl-formButtonPrimary, button:has-text("Continue")').first();

    if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      if (await firstNameInput.isVisible().catch(() => false)) {
        await firstNameInput.fill('Test');
        const lastNameInput = page.locator('input[name="lastName"]').first();
        if (await lastNameInput.isVisible().catch(() => false)) {
          await lastNameInput.fill('Debug');
        }
      }
      await emailInput.fill('test+helmdebug@example.com');
      if (await passwordInput.isVisible().catch(() => false)) {
        await passwordInput.fill('TestHelmDebug123!');
      }
      
      results.signupFormFilled = true;
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '11-signup-filled.png'), fullPage: true });
      
      if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await continueBtn.click();
        await page.waitForTimeout(8000);
        results.signupAfterSubmit = {
          url: page.url(),
          text: await page.evaluate(() => document.body.innerText.slice(0, 1500)),
        };
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, '12-signup-after-submit.png'), fullPage: true });
        
        // Check for error messages
        const errors = await page.locator('.cl-formFieldErrorText, .cl-alertText, [class*="error"], [role="alert"]').allTextContents();
        results.signupErrors = errors;
      }
    }

    // === GOOGLE OAUTH with popup tracking ===
    console.log('=== GOOGLE OAUTH ===');
    await context.clearCookies();
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    
    const googleBtn = page.locator('.cl-socialButtonsBlockButton:has-text("Google"), button:has-text("Google")').first();
    if (await googleBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      const [popup] = await Promise.all([
        page.waitForEvent('popup', { timeout: 5000 }).catch(() => null),
        googleBtn.click(),
      ]);
      
      if (popup) {
        results.googleOAuth = {
          popupOpened: true,
          popupUrl: popup.url(),
        };
        await popup.waitForTimeout(3000).catch(() => {});
        results.googleOAuth.popupTitle = await popup.title().catch(() => 'unknown');
        results.googleOAuth.popupText = await popup.evaluate(() => document.body?.innerText?.slice(0, 1000) || '').catch(() => '');
        await popup.screenshot({ path: path.join(SCREENSHOT_DIR, '13-google-popup.png'), fullPage: true }).catch(() => {});
      } else {
        results.googleOAuth = { popupOpened: false, note: 'No popup opened within 5s' };
      }
      await page.waitForTimeout(2000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '14-after-google-click.png'), fullPage: true });
    }

    // === Check /api/auth/me and /api/auth/clerk/exchange ===
    console.log('=== DIRECT API CHECKS ===');
    const apiChecks = {};
    for (const endpoint of ['/api/auth/me', '/api/auth/clerk/exchange', '/api/auth/config', '/api/auth/logout']) {
      try {
        const res = await page.evaluate(async ({ base, ep }) => {
          const r = await fetch(`${base}${ep}`, { credentials: 'include' });
          return { status: r.status, body: await r.text(), headers: Object.fromEntries(r.headers.entries()) };
        }, { base: BASE_URL, ep: endpoint });
        apiChecks[endpoint] = res;
      } catch (e) {
        apiChecks[endpoint] = { error: e.message };
      }
    }
    results.directApiChecks = apiChecks;

    // === Check Clerk instance details ===
    results.clerkInstanceAnalysis = {
      publishableKey: 'pk_live_Y2F1c2FsLWNhcmlib3UtMjM1Mi5jbGVyay5hY2NvdW50cy5kZXYk',
      decodedDomain: Buffer.from('Y2F1c2FsLWNhcmlib3UtMjM1Mi5jbGVyay5hY2NvdW50cy5kZXYk', 'base64').toString(),
      keyPrefix: 'pk_live_',
      showsDevelopmentMode: true,
      backendSaysLive: true,
      mismatch: 'pk_live_ key points to *.clerk.accounts.dev (development instance), UI shows "Development mode" badge',
    };

    // === /app redirect test ===
    await context.clearCookies();
    await page.goto(`${BASE_URL}/app`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    results.appRedirect = {
      finalUrl: page.url(),
      redirected: page.url() !== `${BASE_URL}/app`,
    };

  } catch (error) {
    results.fatalError = { message: error.message, stack: error.stack };
  } finally {
    await browser.close();
  }

  fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
  console.log('\n=== SUMMARY ===');
  console.log('Failed requests:', results.failedRequests.length);
  results.failedRequests.forEach(r => console.log(`  ${r.status} ${r.method} ${r.url}\n    ${r.body?.slice(0, 200)}`));
  console.log('\nAPI calls:', results.apiCalls.map(a => `${a.status} ${a.url}`));
  console.log('\nClerk calls (non-200):', results.clerkCalls.filter(c => c.status >= 400).map(c => `${c.status} ${c.url}`));
  console.log('\nConsole errors:', results.consoleErrors.map(e => e.text));
  console.log('\nSignup after submit:', JSON.stringify(results.signupAfterSubmit, null, 2));
  console.log('\nSignup errors:', results.signupErrors);
  console.log('\nGoogle OAuth:', JSON.stringify(results.googleOAuth, null, 2));
  console.log('\nDirect API checks:', JSON.stringify(results.directApiChecks, null, 2));
}

main().catch(console.error);
