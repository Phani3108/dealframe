// Screenshot script for TemporalOS dashboard pages
const puppeteer = require('/tmp/ss/node_modules/puppeteer')
const path = require('path')
const fs = require('fs')

const BASE = 'http://localhost:3001'
const OUT = path.resolve(__dirname, '..', 'docs', 'screenshots')
fs.mkdirSync(OUT, { recursive: true })

const PAGES = [
  { name: 'dashboard',       url: '/',                title: 'Dashboard' },
  { name: 'upload',          url: '/upload',          title: 'Upload & Process' },
  { name: 'search',          url: '/search',          title: 'Search' },
  { name: 'chat',            url: '/chat',            title: 'Ask Library' },
  { name: 'coaching',        url: '/coaching',        title: 'Coaching' },
  { name: 'schema-builder',  url: '/schema-builder',  title: 'Schema Builder' },
  { name: 'batch',           url: '/batch',           title: 'Batch Processing' },
  { name: 'meeting-prep',    url: '/meeting-prep',    title: 'Meeting Prep' },
  { name: 'knowledge-graph', url: '/knowledge-graph', title: 'Knowledge Graph' },
  { name: 'integrations',    url: '/integrations',    title: 'Integrations' },
  { name: 'observability',   url: '/observability',   title: 'Observability' },
]

;(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900 },
  })

  for (const { name, url, title } of PAGES) {
    try {
      const page = await browser.newPage()
      await page.goto(`${BASE}${url}`, { waitUntil: 'networkidle2', timeout: 15000 })
      await new Promise(r => setTimeout(r, 2000)) // let animations + API calls settle
      const file = path.join(OUT, `${name}.png`)
      await page.screenshot({ path: file, fullPage: false })
      console.log(`✓ ${title} → ${name}.png`)
      await page.close()
    } catch (e) {
      console.error(`✗ ${title}: ${e.message}`)
    }
  }

  await browser.close()
  console.log('\nDone! Screenshots saved to docs/screenshots/')
})()
