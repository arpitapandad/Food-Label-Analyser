/**
 * Thin client for the FastAPI backend.
 *
 * All paths are RELATIVE. In dev, Vite proxies them to :8000; in production
 * FastAPI serves this app itself, so they resolve to the same origin either way.
 */

/** Turn a non-2xx response into a readable Error, surfacing FastAPI's `detail`. */
async function readResponse(response) {
  if (response.ok) return response.json()

  let detail = `Request failed (HTTP ${response.status})`
  try {
    const body = await response.json()
    if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch {
    // Non-JSON error body (e.g. a proxy failure) - keep the generic message.
  }
  const error = new Error(detail)
  error.status = response.status
  return Promise.reject(error)
}

/** Liveness + which OCR engine and LLM are wired up. */
export async function getHealth() {
  return readResponse(await fetch('/health'))
}

/** The claims this rule engine can actually evaluate (drives the chips). */
export async function getClaims() {
  return readResponse(await fetch('/claims'))
}

/**
 * Distinct categories present in the curated dataset.
 *
 * Also feeds the rule engine: a category lets it infer solid vs liquid, and it
 * adds the category bonus when ranking similar products.
 */
export async function getCategories() {
  return readResponse(await fetch('/categories'))
}

/**
 * OCR only: read the two label photos and return the extracted values,
 * WITHOUT deciding a verdict. Lets the user confirm/correct before checking.
 *
 * `{ ingredientsFile, panelFile }` are File objects or null.
 */
export async function extractLabel({ ingredientsFile, panelFile }) {
  const body = new FormData()
  if (ingredientsFile) body.append('ingredients_file', ingredientsFile)
  if (panelFile) body.append('panel_file', panelFile)

  return readResponse(
    await fetch('/ocr/extract', {
      method: 'POST',
      body,
    }),
  )
}

/**
 * Decide the verdict from confirmed values.
 *
 * `payload` = { claim, panel, ingredients, label_text, form, category, use_llm }
 */
export async function verifyClaim(payload) {
  return readResponse(
    await fetch('/verify/json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )
}
