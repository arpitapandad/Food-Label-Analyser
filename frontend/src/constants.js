/**
 * Shared display constants and the verdict-mapping logic.
 *
 * The verdict mapping is the heart of the UI: it turns the backend's two
 * independent booleans into the single "True / Misleading / False" badge the
 * design calls for.
 */

/** Editable nutrition fields, in the order they appear on Indian labels. */
export const PANEL_FIELDS = [
  { key: 'energy_kcal', label: 'Energy', unit: 'kcal' },
  { key: 'protein_g', label: 'Protein', unit: 'g' },
  { key: 'carbohydrates_g', label: 'Carbohydrates', unit: 'g' },
  { key: 'total_sugars_g', label: 'Total sugars', unit: 'g' },
  { key: 'added_sugars_g', label: 'Added sugars', unit: 'g' },
  { key: 'dietary_fibre_g', label: 'Dietary fibre', unit: 'g' },
  { key: 'total_fat_g', label: 'Total fat', unit: 'g' },
  { key: 'saturated_fat_g', label: 'Saturated fat', unit: 'g' },
  { key: 'sodium_mg', label: 'Sodium', unit: 'mg' },
]

/**
 * Map a backend decision to the traffic-light verdict shown to the user.
 *
 *   TRUE       - passes the FSSAI threshold and nothing sneaky in the ingredients
 *   MISLEADING - passes the letter of the rule, but the ingredients hide the truth
 *                (e.g. "No Added Sugar" + apple juice concentrate)
 *   FALSE      - fails the rule, or the claim itself is prohibited
 */
export function verdictOf(decision) {
  const status = decision?.status

  if (status === 'PROHIBITED') {
    return {
      key: 'false',
      label: 'Not allowed',
      headline: 'This claim is prohibited',
      blurb:
        'FSSAI does not permit this wording on a food label. A food may describe its nutrition, but it may not claim to prevent, treat or cure disease.',
    }
  }

  if (status === 'UNKNOWN_CLAIM') {
    return {
      key: 'unknown',
      label: 'Not checked',
      headline: 'Outside the Phase-1 rule set',
      blurb:
        'This claim is not one of the claims covered by this rule set, so no pass/fail decision was made.',
    }
  }

  if (status === 'INSUFFICIENT_DATA') {
    const missing = (decision?.missing_fields || []).join(', ')
    return {
      key: 'incomplete',
      label: 'Need more data',
      headline: 'Not enough information to decide',
      blurb: missing
        ? `The nutrition panel did not give us: ${missing}. Add the value and check again.`
        : 'The nutrition panel did not give us the value this claim depends on.',
    }
  }

  const compliant = decision?.is_technically_compliant

  if (compliant === true && decision?.is_deceptive) {
    return {
      key: 'misleading',
      label: 'Misleading',
      headline: 'Technically compliant — but deceptive',
      blurb:
        'It satisfies the letter of the FSSAI rule, yet an ingredient in the list tells a different story. This is the health-halo effect in action.',
    }
  }

  if (compliant === true) {
    return {
      key: 'true',
      label: 'True',
      headline: 'The claim holds up',
      blurb: 'The nutrition values satisfy the FSSAI requirement for this claim, and nothing in the ingredient list contradicts it.',
    }
  }

  return {
    key: 'false',
    label: 'False',
    headline: 'The claim does not hold up',
    blurb: 'The nutrition values fall short of the FSSAI requirement for this claim.',
  }
}

/** Number of scans required before the check can run. */
export const SCAN_SLOTS = [
  {
    id: 'ingredients',
    title: 'Scan 1: Ingredient List',
    hint: 'The "Ingredients:" panel on the back of the pack',
  },
  {
    id: 'panel',
    title: 'Scan 2: Nutritional Value Table',
    hint: 'The per 100 g / per serving nutrition grid',
  },
]

export const HISTORY_KEY = 'ure.scanHistory.v1'
export const HISTORY_LIMIT = 20
