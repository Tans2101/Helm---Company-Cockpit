import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'https://helm-company-cockpit.vercel.app';
const SCREENSHOT_DIR = '/workspace/helm-debug/screenshots';
const RESULTS_FILE = '/workspace/helm-debug/results.json';

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const results = {
  timestamp: new Date().toISOString(),
  jsBundleHash: 'main.a37ad191.js',
  apiCalls: [],
  failedRequests: [],
  consoleErrors: [],
  consoleWarnings: [],
  steps: [],
};

function recordStep(name, data) {
  results.steps.push({ name, ...data, timestamp: new Date().toISOString() });
  console.log(`\n=== STEP: ${name} ===`);
  console.log(JSON.stringify(data, null, 2));
}

async function getVisibleText(page) {
  return page.evaluate(() => {
    const body = document.body;
    if (!body) return '';
    const clone = body.cloneNode(true);
    clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
    return clone.innerText.replace(/\s+/g, ' ').trim().slice(0, 2000);
  });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  // Capture all network requests
  page.on('request', (request) => {
    const url = request.url();
    if (url.includes('/api/')) {
      results.apiCalls.push({
        type: 'request',
        method: request.method(),
        url,
        time: new Date().toISOString(),
      });
    }
  });

  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/api/')) {
      let body = '';
      try {
        const ct = response.headers()['content-type'] || '';
        if (ct.includes('json') || ct.includes('text')) {
          body = await response.text();
        }
      } catch (e) {
        body = `[could not read body: ${e.message}]`;
      }
      const entry = {
        type: 'response',
        method: response.request().method(),
        url,
        status: response.status(),
        statusText: response.statusText(),
        body: body.slice(0, 5000),
        time: new Date().toISOString(),
      };
      results.apiCalls.push(entry);
      if (response.status() >= 400) {
        results.failedRequests.push(entry);
      }
    }
  });

  page.on('requestfailed', (request) => {
    const url = request.url();
    if (url.includes('/api/')) {
      results.failedRequests.push({
        type: 'requestfailed',
        method: request.method(),
        url,
        failure: request.failure()?.errorText || 'unknown',
        time: new Date().toISOString(),
      });
    }
  });

  page.on('console', (msg) => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error') {
      results.consoleErrors.push({ text, time: new Date().toISOString() });
    } else if (type === 'warning') {
      results.consoleWarnings.push({ text, time: new Date().toISOString() });
    }
  });

  page.on('pageerror', (error) => {
    results.consoleErrors.push({ text: `PAGE ERROR: ${error.message}`, time: new Date().toISOString() });
  });

  try {
    // Step 1: Sign-up page
    await page.goto(`${BASE_URL}/sign-up`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    const signupScreenshot = path.join(SCREENSHOT_DIR, '01-sign-up.png');
    await page.screenshot({ path: signupScreenshot, fullPage: true });
    const signupUrl = page.url();
    const signupText = await getVisibleText(page);
    recordStep('sign-up-page', { url: signupUrl, visibleText: signupText, screenshot: signupScreenshot });

    // Step 3: Try sign-up flow
    // Look for Google button
    const googleBtn = page.locator('button:has-text("Google"), [data-provider="google"], .cl-socialButtonsBlockButton:has-text("Google")').first();
    const emailInput = page.locator('input[type="email"], input[name="emailAddress"], input[name="identifier"]').first();
    
    let signupAttempt = { method: 'none', result: 'no action taken' };
    
    if (await googleBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      signupAttempt.method = 'google';
      try {
        await googleBtn.click();
        await page.waitForTimeout(3000);
        signupAttempt.result = 'clicked';
        signupAttempt.urlAfterClick = page.url();
        signupAttempt.visibleTextAfterClick = await getVisibleText(page);
        const googleScreenshot = path.join(SCREENSHOT_DIR, '02-after-google-click.png');
        await page.screenshot({ path: googleScreenshot, fullPage: true });
        signupAttempt.screenshot = googleScreenshot;
      } catch (e) {
        signupAttempt.result = `error: ${e.message}`;
      }
    } else if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      signupAttempt.method = 'email';
      try {
        await emailInput.fill('test+helmdebug@example.com');
        // Look for continue/submit button
        const continueBtn = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Sign up"), .cl-formButtonPrimary').first();
        if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await continueBtn.click();
          await page.waitForTimeout(5000);
          signupAttempt.result = 'submitted email';
        } else {
          await emailInput.press('Enter');
          await page.waitForTimeout(5000);
          signupAttempt.result = 'pressed enter on email';
        }
        signupAttempt.urlAfterSubmit = page.url();
        signupAttempt.visibleTextAfterSubmit = await getVisibleText(page);
        const emailScreenshot = path.join(SCREENSHOT_DIR, '02-after-email-submit.png');
        await page.screenshot({ path: emailScreenshot, fullPage: true });
        signupAttempt.screenshot = emailScreenshot;
      } catch (e) {
        signupAttempt.result = `error: ${e.message}`;
      }
    } else {
      // Try to find any Clerk elements
      const clerkRoot = await page.locator('#clerk-components, .cl-rootBox, [class*="cl-"]').count();
      signupAttempt.clerkElementsFound = clerkRoot;
      signupAttempt.pageHtml = await page.content().then(h => h.slice(0, 3000));
    }
    recordStep('sign-up-attempt', signupAttempt);

    // Step 4: Login page (fresh context to avoid state)
    await context.clearCookies();
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    const loginScreenshot = path.join(SCREENSHOT_DIR, '03-login.png');
    await page.screenshot({ path: loginScreenshot, fullPage: true });
    const loginUrl = page.url();
    const loginText = await getVisibleText(page);
    recordStep('login-page', { url: loginUrl, visibleText: loginText, screenshot: loginScreenshot });

    // Try login with email
    const loginEmailInput = page.locator('input[type="email"], input[name="emailAddress"], input[name="identifier"]').first();
    let loginAttempt = { method: 'none' };
    if (await loginEmailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      loginAttempt.method = 'email';
      await loginEmailInput.fill('test+helmdebug@example.com');
      const continueBtn = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Sign in"), .cl-formButtonPrimary').first();
      if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await continueBtn.click();
        await page.waitForTimeout(5000);
      }
      loginAttempt.urlAfterSubmit = page.url();
      loginAttempt.visibleTextAfterSubmit = await getVisibleText(page);
      const loginAfterScreenshot = path.join(SCREENSHOT_DIR, '04-after-login-attempt.png');
      await page.screenshot({ path: loginAfterScreenshot, fullPage: true });
      loginAttempt.screenshot = loginAfterScreenshot;
    }
    recordStep('login-attempt', loginAttempt);

    // Step 5: Navigate to /app without auth
    await context.clearCookies();
    await page.goto(`${BASE_URL}/app`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    const appScreenshot = path.join(SCREENSHOT_DIR, '05-app-no-auth.png');
    await page.screenshot({ path: appScreenshot, fullPage: true });
    const appUrl = page.url();
    const appText = await getVisibleText(page);
    recordStep('app-no-auth', { 
      url: appUrl, 
      visibleText: appText, 
      screenshot: appScreenshot,
      redirected: appUrl !== `${BASE_URL}/app`,
    });

    // Fetch auth config directly for comparison
    const configResponse = await page.evaluate(async (base) => {
      const res = await fetch(`${base}/api/auth/config`);
      return { status: res.status, body: await res.text() };
    }, BASE_URL);
    results.authConfig = configResponse;

    // Check Clerk key in page
    const clerkKeyInPage = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script'));
      const html = document.documentElement.outerHTML;
      const match = html.match(/pk_(live|test)_[A-Za-z0-9._$-]+/);
      return match ? match[0] : null;
    });
    results.clerkKeyInPage = clerkKeyInPage;

    // Final stuck state
    results.stuckState = {
      url: page.url(),
      visibleText: await getVisibleText(page),
    };

  } catch (error) {
    results.fatalError = error.message;
    console.error('Fatal error:', error);
    try {
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'error.png'), fullPage: true });
    } catch {}
  } finally {
    await browser.close();
  }

  fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
  console.log('\n\n=== FINAL RESULTS ===');
  console.log(JSON.stringify(results, null, 2));
}

main().catch(console.error);
