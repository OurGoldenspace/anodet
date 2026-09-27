import { expect, test } from "@playwright/test"

const passphrase = process.env.SHOP_PASSPHRASE || "sample-shop"

test("NASA Engine 31 remembered case is reused on Engine 74", async ({ page, request }) => {
  const session = await request.post("http://127.0.0.1:8001/session", {
    data: { name: "Pat", passphrase },
  })
  expect(session.ok()).toBeTruthy()
  const body = (await session.json()) as { token: string }
  const emptied = await request.post("http://127.0.0.1:8001/demo/empty", {
    headers: { Authorization: `Bearer ${body.token}` },
  })
  expect(emptied.ok()).toBeTruthy()

  await page.goto("/")
  await page.evaluate(() => {
    window.localStorage.clear()
  })
  await page.reload()

  await page.getByTestId("sign-in-name").fill("Pat")
  await page.getByTestId("sign-in-passphrase").fill(passphrase)
  await page.getByTestId("sign-in-submit").click()
  await page.getByTestId("path-nasa").click()

  await page.getByTestId("engine-31").click()
  await page.getByTestId("case-cause").fill("Hot-section wear confirmed on the cheap checks")
  await page.getByTestId("remember-case").click()
  await expect(page.getByText(/Remembered/)).toBeVisible()

  const recall = page.getByTestId("open-recall")
  if (await recall.isVisible()) await recall.click()
  else await page.getByTestId("engine-74").click()

  await expect(page.getByText(/Same signature as Engine 31/i).first()).toBeVisible()
})
