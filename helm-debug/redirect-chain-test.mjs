import { chromium } from 'playwright';
import fs from 'fs';

const BASE = 'https://helm-company-cockpit.vercel.app';
const OUT = '/workspace/helm-debug/redirect-chain-results.json';

const results = {
  timestamp: new Date().toISOString(),
  signInEmbedded: null,
  signInDetails: {},
  redirectChain: [],
  navigationEvents: [],
  clerkRequests: [],
  oauthStartUrl: null,
};

function pushUrl(label, url, extra = {}) {
  results.redirectChain.push({ step: results.redirectChain.length + 1, label, url, ...extra });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) {
      results.navigationEvents.push({ type: 'navigate', url: frame.url(), time: Date.now() });
    }
  });

  page.on('response', async (res) => {
    const url = res.url();
    if (!url.includes('clerk') && !url.includes('accounts.dev') && !url.includes('accounts.google')) return;
    let body = '';
    if (res.status() >= 300 && res.status() < 400) {
      body = `redirect -> ${res.headers()['location'] || ''}`;
    } else if (url.includes('/v1/environment') || url.includes('/v1/client')) {
      try { body = (await res.text()).slice(0, 500); } catch {}
    }
    results.clerkRequests.push({ url, status: res.status(), method: res.request().method(), body: body.slice(0, 800) });
  });

  pushUrl('start', `${BASE}/login`);

  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  const gotIt = page.locator('button:has-text("Got it")');
  if (await gotIt.isVisible({ timeout: 1500 }).catch(() => false)) await gotIt.click();

  const loginUrl = page.url();
  pushUrl('after-load', loginUrl);

  // Inspect SignIn embedding
  const clerkRoot = page.locator('[data-testid="clerk-sign-in"]');
  const clerkComponent = page.locator('.cl-rootBox, .cl-signIn-root, .cl-card');
  const hostedRedirect = loginUrl.includes('clerk.accounts.dev') || loginUrl.includes('accounts.dev/sign-in');

  results.signInEmbedded = !hostedRedirect && (await clerkRoot.count()) > 0;
  results.signInDetails = {
    pageUrl: loginUrl,
    onClerkHostedPage: hostedRedirect,
    clerkSignInTestId: await clerkRoot.count(),
    clerkRootBoxes: await clerkComponent.count(),
    hasGoogleButton: await page.locator('button:has-text("Google"), .cl-socialButtonsBlockButton').count(),
    hasDevelopmentBadge: (await page.locator('text=Development mode').count()) > 0,
    bodySnippet: (await page.evaluate(() => document.body.innerText)).slice(0, 600),
    iframeCount: await page.locator('iframe').count(),
  };

  pushUrl('sign-in-inspection', loginUrl, { embedded: results.signInEmbedded });

  // Click Google and trace redirects
  const googleBtn = page.locator('.cl-socialButtonsBlockButton:has-text("Google"), button:has-text("Google")').first();
  if (await googleBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    const beforeClick = page.url();
    pushUrl('before-google-click', beforeClick);

    await googleBtn.click();
    await page.waitForTimeout(6000);

    let current = page.url();
    pushUrl('after-google-click', current);

    // Follow intermediate redirects by waiting
    for (let i = 0; i < 3; i++) {
      await page.waitForTimeout(2000);
      const next = page.url();
      if (next !== current) {
        pushUrl(`redirect-${i + 1}`, next);
        current = next;
      }
    }

    results.oauthStartUrl = current;

    // Parse Google OAuth redirect_uri from URL if on Google
    if (current.includes('accounts.google.com')) {
      const u = new URL(current);
      results.googleOAuthParams = {
        redirect_uri: u.searchParams.get('redirect_uri'),
        client_id: u.searchParams.get('client_id'),
        state: u.searchParams.get('state')?.slice(0, 40),
      };
      pushUrl('google-oauth-page', current, results.googleOAuthParams);
    }
  } else {
    results.signInDetails.googleButtonMissing = true;
  }

  results.finalUrl = page.url();
  results.leftHelmAt = results.redirectChain.find((s) =>
    s.url && !s.url.startsWith(BASE) && !s.url.includes('accounts.google.com')
  ) || null;

  await browser.close();
  fs.writeFileSync(OUT, JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
