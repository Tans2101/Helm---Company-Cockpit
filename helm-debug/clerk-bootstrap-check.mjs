import { chromium } from 'playwright';

const BASE_URL = 'https://helm-company-cockpit.vercel.app';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const clerkCalls = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (!url.includes('clerk.accounts.dev/v1/')) return;
    let body = '';
    try { body = (await response.text()).slice(0, 300); } catch {}
    clerkCalls.push({ url: url.split('?')[0], status: response.status(), body });
  });

  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(5000);

  const devBrowser401 = clerkCalls.filter((c) => c.status === 401);
  const devBrowser200 = clerkCalls.filter((c) => c.status === 200);
  const recovered = devBrowser401.length > 0 && devBrowser200.some((c) => c.url.includes('/environment') || c.url.includes('/client'));

  console.log(JSON.stringify({
    totalClerkV1Calls: clerkCalls.length,
    calls: clerkCalls,
    initial401Count: devBrowser401.length,
    later200Count: devBrowser200.length,
    clerkRecoveredAfterDevBrowser: recovered,
  }, null, 2));

  await browser.close();
}

main();
