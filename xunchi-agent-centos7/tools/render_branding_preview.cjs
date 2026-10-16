// Development-only browser rendering. This does not run the OpenCode TUI.
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createRequire } = require('node:module');
const load = process.env.XUNCHI_NODE_MODULES
  ? createRequire(path.join(process.env.XUNCHI_NODE_MODULES, 'package.json'))
  : require;
const { chromium } = load('playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const url = pathToFileURL(path.join(root, 'branding/startup-preview.html')).href;
  const options = { headless: true };
  if (process.env.XUNCHI_BROWSER_EXECUTABLE) options.executablePath = process.env.XUNCHI_BROWSER_EXECUTABLE;
  const browser = await chromium.launch(options);
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  const checks = [];
  for (const size of [{ width: 1360, height: 900 }, { width: 720, height: 700 }, { width: 500, height: 700 }]) {
    await page.setViewportSize(size);
    const result = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > window.innerWidth,
      markVisible: getComputedStyle(document.querySelector('.mark')).display !== 'none',
      englishVisible: getComputedStyle(document.querySelector('.english')).display !== 'none',
      company: document.querySelector('.company-name').textContent,
      product: document.querySelector('.product').textContent,
    }));
    if (result.overflow) throw new Error('Preview overflows at width ' + size.width);
    checks.push({ ...size, ...result });
    await page.screenshot({ path: path.join(root, 'branding/startup-preview-' + size.width + '.png'), fullPage: true });
  }
  await browser.close();
  if (errors.length) throw new Error(errors.join('\n'));
  fs.writeFileSync(path.join(root, 'branding/preview-check.json'), JSON.stringify({
    kind: 'static HTML preview only; not actual TUI validation', checks, pageErrors: errors,
  }, null, 2) + '\n');
  console.log('Static preview rendered; 3 viewport checks passed. Actual TUI not tested.');
})().catch(error => { console.error(error); process.exitCode = 1; });
