import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'https://helm-company-cockpit.vercel.app';
const SCREENSHOT_DIR = '/workspace/helm-debug/screenshots';
const RESULTS_FILE = '/workspace/helm-debug/login-retest-results.json';

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const results = {
  timestamp: new Date().toISOString(),
  testUrl: `${BASE_URL}/login`,
  consoleMessages: [],
  devBrowserUnauthenticatedErrors: [],
  clerkFailedRequests: [],
  exchangeCalls: [],
  apiCalls: [],
  networkSummary: {},
  pageText: '',
  developmentModeVisible: false,
  googleOAuth: {},
};

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  page.on('console', (msg) => {
    const entry = { type: msg.type(), text: msg.text() };
    results.consoleMessages.push(entry);
    if (entry.text.includes('dev_browser_unauthenticated') || entry.text.includes('Browser unauthenticated')) {
      results.devBrowserUnauthenticatedErrors.push(entry);
    }
  });

  page.on('pageerror', (error) => {
    results.consoleMessages.push({ type: 'pageerror', text: error.message });
    if (error.message.includes('dev_browser_unauthenticated') || error.message.includes('Browser unauthenticated')) {
      results.devBrowserUnauthenticatedErrors.push({ type: 'pageerror', text: error.message });
    }
  });

  page.on('response', async (response) => {
    const url = response.url();
    const status = response.status();
    const method = response.request().method();

    if (url.includes('/api/auth/clerk/exchange')) {
      let body = '';
      try { body = (await response.text()).slice(0, 2000); } catch {}
      results.exchangeCalls.push({ url, status, method, body });
    }

    if (url.includes('/api/')) {
      let body = '';
      try {
        const ct = response.headers()['content-type'] || '';
        if (ct.includes('json')) body = (await response.text()).slice(0, 1000);
      } catch {}
      results.apiCalls.push({ url, status, method, body });
    }

    if ((url.includes('clerk') || url.includes('accounts.dev')) && status >= 400) {
      let body = '';
      try { body = (await response.text()).slice(0, 1000); } catch {}
      results.clerkFailedRequests.push({ url, status, method, body });
      if (body.includes('dev_browser_unauthenticated')) {
        results.devBrowserUnauthenticatedErrors.push({
          type: 'network',
          text: `${status} ${method} ${url}: ${body}`,
        });
      }
    }
  });

  const popupEvents = [];
  page.on('popup', (popup) => {
    popupEvents.push({ initialUrl: popup.url(), time: Date.now() });
  });

  try {
    console.log('Visiting /login with fresh context...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 45000 });
    await page.waitForTimeout(4000);

    const cookieBtn = page.locator('button:has-text("Got it")');
    if (await cookieBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cookieBtn.click();
      await page.waitForTimeout(500);
    }

    results.pageText = await page.evaluate(() => document.body.innerText);
    results.developmentModeVisible = results.pageText.includes('Development mode');

    const authConfigRes = results.apiCalls.find((c) => c.url.includes('/api/auth/config'));
    results.authConfig = authConfigRes ? { status: authConfigRes.status, body: authConfigRes.body } : null;

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'login-retest-initial.png'),
      fullPage: true,
    });

    console.log('Clicking Google sign-in...');
    const googleBtn = page.locator('.cl-socialButtonsBlockButton:has-text("Google"), button:has-text("Google")').first();
    const googleVisible = await googleBtn.isVisible({ timeout: 5000 }).catch(() => false);
    results.googleOAuth.buttonVisible = googleVisible;

    if (googleVisible) {
      const popupPromise = page.waitForEvent('popup', { timeout: 8000 }).catch(() => null);
      const navPromise = page.waitForURL(/accounts\.google\.com|clerk\.accounts|oauth/, { timeout: 8000 }).catch(() => null);

      await googleBtn.click();
      await page.waitForTimeout(5000);

      const popup = await popupPromise;
      const navigated = await navPromise;

      if (popup) {
        await popup.waitForLoadState('domcontentloaded', { timeout: 8000 }).catch(() => {});
        await popup.waitForTimeout(2000);
        const popupUrl = popup.url();
        results.googleOAuth = {
          ...results.googleOAuth,
          popupOpened: true,
          popupUrl,
          popupTitle: await popup.title().catch(() => ''),
          reachedGoogle: popupUrl.includes('accounts.google.com'),
          reachedClerk: popupUrl.includes('clerk') || popupUrl.includes('accounts.dev'),
        };
        await popup.screenshot({
          path: path.join(SCREENSHOT_DIR, 'login-retest-google-popup.png'),
          fullPage: true,
        }).catch(() => {});
      } else {
        const currentUrl = page.url();
        results.googleOAuth = {
          ...results.googleOAuth,
          popupOpened: false,
          mainPageUrl: currentUrl,
          reachedGoogle: currentUrl.includes('accounts.google.com'),
          redirectedInSameTab: navigated !== null,
        };
      }

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, 'login-retest-after-google-click.png'),
        fullPage: true,
      });
    }

    results.networkSummary = {
      totalApiCalls: results.apiCalls.length,
      exchangeCallCount: results.exchangeCalls.length,
      clerkFailedCount: results.clerkFailedRequests.length,
      devBrowserErrorCount: results.devBrowserUnauthenticatedErrors.length,
    };

  } catch (error) {
    results.fatalError = { message: error.message, stack: error.stack };
  } finally {
    await browser.close();
  }

  fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));

  console.log('\n=== LOGIN RE-TEST SUMMARY ===');
  console.log('Development mode visible:', results.developmentModeVisible);
  console.log('dev_browser_unauthenticated errors:', results.devBrowserUnauthenticatedErrors.length);
  console.log('Clerk failed requests:', results.clerkFailedRequests.length);
  console.log('Exchange calls:', results.exchangeCalls.length, results.exchangeCalls.map((c) => `${c.method} ${c.status}`));
  console.log('Google OAuth:', JSON.stringify(results.googleOAuth, null, 2));
  console.log('Auth config:', results.authConfig?.body || 'not captured');
}

main().catch(console.error);
