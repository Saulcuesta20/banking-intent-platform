import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { createCatalogFixtures } from './fixtures/catalog'

const fixtures = createCatalogFixtures()
const API_BASE = 'http://127.0.0.1:8030'
const screenshotPath = path.resolve('tests/e2e/screenshots/business-model-editor.png')

async function stubLauncherApis(page: import('@playwright/test').Page) {
  await page.route(`${API_BASE}/launcher/home`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fixtures.home) }),
  )

  await page.route(new RegExp(`${API_BASE}/catalog/metadata.*`), (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fixtures.metadata) }),
  )

  await page.route('**/catalog/assets**', (route) => {
    const url = route.request().url()
    if (url.includes('/catalog/assets?')) {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fixtures.catalogAssetsResponse) })
      return
    }
    if (url.includes(`/catalog/assets/${fixtures.assetDetail.asset_id}`)) {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(fixtures.assetDetail) })
      return
    }
    route.continue()
  })
}

test('business model editor renders graph context for the knowledge base', async ({ page }) => {
  await stubLauncherApis(page)
  await page.goto('/')
  await page.waitForFunction(() => {
    const root = document.getElementById('root')
    return Boolean(root && root.querySelector('button'))
  })

  await page.getByRole('button', { name: /assets/i }).click()
  await page.getByRole('button', { name: /Everyday Banking Graph/i }).click()
  const editButton = page.locator('.asset-view-switch').getByRole('button', { name: 'Editar' })
  await expect(editButton).toBeVisible()
  await editButton.click()

  await expect(page.getByRole('button', { name: 'Canvas KB' })).toBeVisible()
  await expect(page.getByLabel('Knowledge base')).toBeVisible()
  await expect(page.getByText('Ontology selection')).toBeVisible()

  await page.getByRole('button', { name: 'Raw Source' }).click()
  const rawSource = page.locator('textarea').first()
  await expect(rawSource).toContainText('entity.everyday_banking_graph')

  fs.mkdirSync(path.dirname(screenshotPath), { recursive: true })
  await page.screenshot({ path: screenshotPath, fullPage: true })
})
