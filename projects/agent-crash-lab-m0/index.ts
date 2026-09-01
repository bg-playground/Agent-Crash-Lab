import { Solari } from "@solarisdk/browser"
import { SolariClient } from "@solarisdk/sdk"

const PORT = 3000
const FAILURE_SEED = 48291

const TARGET_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>ChaosShop Checkout</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 60px auto; padding: 0 24px; }
    .card { border: 1px solid #ddd; border-radius: 16px; padding: 24px; }
    button { font: inherit; padding: 10px 16px; cursor: pointer; }
    #modal { position: fixed; inset: 0; background: rgba(0,0,0,.42); display: grid; place-items: center; }
    #modal > div { background: white; border-radius: 16px; padding: 24px; width: min(420px, 80vw); }
    [hidden] { display: none !important; }
  </style>
</head>
<body>
  <h1>ChaosShop</h1>
  <div class="card">
    <h2>Noise-Canceling Headphones</h2>
    <p>Order total: $249.00</p>
    <p id="status">Ready for shipping selection.</p>
    <button id="primary" onclick="completeTask()">Continue</button>
  </div>

  <div id="modal" hidden>
    <div>
      <h2>Before you continue</h2>
      <p>Review our updated shopping preferences.</p>
      <button onclick="dismissModal()">Continue</button>
    </div>
  </div>

  <script>
    const params = new URLSearchParams(location.search)
    const seed = Number(params.get('seed') || '0')

    // Deterministic mutation: seed 48291 injects an unexpected modal containing
    // a second visible button with the same semantic label as the target action.
    if (seed === ${FAILURE_SEED}) {
      document.querySelector('#modal').hidden = false
      document.body.dataset.mutations = 'unexpected-modal+duplicate-action-label'
    } else {
      document.body.dataset.mutations = 'none'
    }

    function dismissModal() {
      document.querySelector('#modal').hidden = true
    }

    function completeTask() {
      document.querySelector('#status').textContent = 'Shipping step reached. Stop before payment.'
      document.querySelector('#primary').disabled = true
      document.body.dataset.taskComplete = 'true'
    }
  </script>
</body>
</html>`

type Trial = {
  label: string
  seed: number
  passed: boolean
  sessionId: string
  replayUrl?: string
  error?: string
}

async function waitForReplay(solari: Solari, sessionId: string): Promise<string | undefined> {
  for (let attempt = 1; attempt <= 10; attempt++) {
    try {
      const { url } = await solari.sessions.getReplayUrl(sessionId)
      return url
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 3000))
    }
  }
  return undefined
}

async function runTrial(solari: Solari, targetUrl: string, label: string, seed: number): Promise<Trial> {
  const browser = await solari.launch({ recording: true })
  const sessionId = browser.id
  let passed = false
  let error: string | undefined

  try {
    const page = await browser.newPage()
    await page.goto(`${targetUrl}?seed=${seed}`, { waitUntil: "networkidle" })

    // M0 deliberately uses a brittle computer-use policy. The point of this
    // milestone is not agent intelligence; it is proving Crash Lab can turn a
    // passing workflow into a deterministic, reproducible failure.
    await page.getByRole("button", { name: "Continue", exact: true }).click()
    passed = (await page.locator("body").getAttribute("data-task-complete")) === "true"
  } catch (err) {
    error = err instanceof Error ? err.message : String(err)
  } finally {
    await browser.close()
  }

  const replayUrl = await waitForReplay(solari, sessionId)
  return { label, seed, passed, sessionId, replayUrl, error }
}

function printTrial(trial: Trial): void {
  console.log(`${trial.passed ? "PASS" : "FAIL"}  ${trial.label}  seed=${trial.seed}`)
  console.log(`      session=${trial.sessionId}`)
  if (trial.replayUrl) console.log(`      replay=${trial.replayUrl}`)
  if (trial.error) console.log(`      error=${trial.error.split("\n")[0]}`)
}

async function main(): Promise<void> {
  if (!process.env.SOLARI_API_KEY) throw new Error("SOLARI_API_KEY is required")

  const platform = new SolariClient({ apiKey: process.env.SOLARI_API_KEY })
  const browserClient = new Solari({ apiKey: process.env.SOLARI_API_KEY })
  const sandbox = await platform.sandboxes.create({ template: "base", timeoutMs: 10 * 60_000 })

  try {
    await sandbox.connect()
    await sandbox.files.write("/tmp/chaosshop/index.html", TARGET_HTML)
    await sandbox.commands.run("sh", {
      args: ["-c", `cd /tmp/chaosshop && nohup python3 -m http.server ${PORT} >/tmp/chaosshop.log 2>&1 &`],
    })

    const { url: targetUrl } = await sandbox.previewUrl(PORT)
    console.log("Agent Crash Lab — M0 deterministic failure proof")
    console.log(`target=${targetUrl}`)

    const baseline = await runTrial(browserClient, targetUrl, "baseline", 0)
    const mutatedA = await runTrial(browserClient, targetUrl, "mutation-a", FAILURE_SEED)
    const mutatedB = await runTrial(browserClient, targetUrl, "mutation-b", FAILURE_SEED)

    console.log("\nRESULTS")
    printTrial(baseline)
    printTrial(mutatedA)
    printTrial(mutatedB)

    const reproduced = baseline.passed && !mutatedA.passed && !mutatedB.passed
    console.log(`\nM0 ${reproduced ? "PROVED" : "NOT PROVED"}`)
    console.log(
      reproduced
        ? `Baseline passes; seed ${FAILURE_SEED} fails twice with the same deterministic mutation.`
        : "Expected one passing baseline and two failing seeded reproductions.",
    )

    if (!reproduced) process.exitCode = 1
  } finally {
    await sandbox.kill()
    await browserClient.close()
  }
}

await main()
