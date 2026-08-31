import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const BASE = 'https://helm-company-cockpit.vercel.app';
const OUT = '/workspace/auth-test-screenshots';
mkdirSync(OUT, { recursive: true });

const results = {
  login: {},
  signup: {},
  appRedirect: {},
  authConfig: {},
  consoleErrors: [],
};

async function run() {
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
  });

  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({ page: page.url(), text: msg.text() });
    }
  });
  page.on('pageerror', (err) => {
    consoleErrors.push({ page: page.url(), text: err.message });
  });

  // 1. Login page
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  const loginUrl = page.url();
  const loginBodyText = await page.locator('body').innerText();
  const loginHtml = await page.content();

  const hasGoogle = /google|continue with google/i.test(loginBodyText + loginHtml);
  const hasEmail = /email|sign in|log in|password/i.test(loginBodyText);
  const hasClerk = /clerk/i.test(loginHtml) || await page.locator('[class*="clerk"], [data-clerk], iframe[src*="clerk"]').count() > 0;
  const loginBlank = loginBodyText.trim().length < 20;

  results.login = {
    url: loginUrl,
    blank: loginBlank,
    bodyTextLength: loginBodyText.trim().length,
    hasGoogleButton: hasGoogle,
    hasEmailForm: hasEmail,
    hasClerkElements: hasClerk,
    bodyPreview: loginBodyText.trim().slice(0, 500),
  };
  await page.screenshot({ path: `${OUT}/01_login.png`, fullPage: true });

  // 5. Network: auth config (during login session)
  const configResp = await page.request.get(`${BASE}/api/auth/config`);
  const configJson = await configResp.json();
  results.authConfig = {
    status: configResp.status(),
    body: configJson,
    clerk_enabled: configJson.clerk_enabled === true,
  };

  results.consoleErrors = consoleErrors.filter((e) => e.page.includes('/login'));

  // 2. Sign-up page
  const page2 = await context.newPage();
  const signupErrors = [];
  page2.on('console', (msg) => {
    if (msg.type() === 'error') signupErrors.push(msg.text());
  });
  page2.on('pageerror', (err) => signupErrors.push(err.message));

  await page2.goto(`${BASE}/sign-up`, { waitUntil: 'networkidle', timeout: 30000 });
  await page2.waitForTimeout(3000);
  const signupBodyText = await page2.locator('body').innerText();
  const signupHtml = await page2.content();

  results.signup = {
    url: page2.url(),
    blank: signupBodyText.trim().length < 20,
    bodyTextLength: signupBodyText.trim().length,
    hasSignUp: /sign up|create.*account|email|google/i.test(signupBodyText + signupHtml),
    hasClerk: /clerk/i.test(signupHtml) || (await page2.locator('[class*="clerk"], iframe[src*="clerk"]').count()) > 0,
    bodyPreview: signupBodyText.trim().slice(0, 500),
    consoleErrors: signupErrors,
  };
  await page2.screenshot({ path: `${OUT}/02_signup.png`, fullPage: true });

  // 3. /app without auth -> redirect to /login
  const page3 = await context.newPage();
  await page3.goto(`${BASE}/app`, { waitUntil: 'networkidle', timeout: 30000 });
  await page3.waitForTimeout(3000);
  const finalUrl = page3.url();
  results.appRedirect = {
    finalUrl,
    redirectedToLogin: finalUrl.includes('/login'),
    bodyPreview: (await page3.locator('body').innerText()).trim().slice(0, 300),
  };
  await page3.screenshot({ path: `${OUT}/03_app_redirect.png`, fullPage: true });

  await browser.close();
  console.log(JSON.stringify(results, null, 2));
}

run().catch((e) => {
  console.error('TEST_FAILED:', e.message);
  process.exit(1);
});
