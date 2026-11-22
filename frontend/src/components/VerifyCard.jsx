import { useRef, useState } from 'react'

import { PANEL_FIELDS, SCAN_SLOTS } from '../constants'

/** Fallback tags if the backend has not answered yet. */
const FALLBACK_CHIPS = [
  'No Added Sugar',
  'High Protein',
  'High Fibre',
  'Low Fat',
  'Low Sodium',
  'Zero Trans Fat',
]

/** Comma-separated input -> a de-duplicated list of individual claims. */
export function splitClaims(raw) {
  const seen = new Set()
  const out = []
  for (const part of String(raw || '').split(',')) {
    const claim = part.trim().replace(/\s+/g, ' ')
    if (!claim) continue
    const key = claim.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(claim)
  }
  return out
}

/**
 * The core card: claim -> two scans -> confirm what we read -> verify.
 *
 * The confirmation step is deliberate. Real photos are noisy, so the user
 * checks the extracted numbers before any verdict is produced.
 */
export default function VerifyCard({
  claim,
  onClaimChange,
  claims,
  form,
  onFormChange,
  categories,
  category,
  onCategoryChange,
  scans,
  onScan,
  onClearScan,
  extracting,
  extractNote,
  panel,
  onPanelChange,
  ingredients,
  onIngredientsChange,
  canVerify,
  verifying,
  onVerify,
  onReset,
  error,
  ocrAvailable,
}) {
  // The input holds one string. Commas split it into separate claims.
  const selected = splitClaims(claim)
  const selectedSet = new Set(selected.map((c) => c.toLowerCase()))

  // Opens the confirmation fields without a photo, so the tool can be tried out
  // and demoed from a desk. Feedback stays honest: the fields the user fills in
  // are the same ones OCR would have seeded.
  const [manualEntry, setManualEntry] = useState(false)

  const chips = (claims.length ? claims.map((c) => c.display_name || c.canonical) : FALLBACK_CHIPS)
    .filter(Boolean)
    .slice(0, 6)

  /** Chips toggle membership rather than replacing the whole field. */
  const toggleChip = (value) => {
    const label = String(value).trim()
    const remaining = selected.filter((c) => c.toLowerCase() !== label.toLowerCase())
    const next = remaining.length === selected.length ? [...selected, label] : remaining
    onClaimChange(next.join(', '))
  }

  // True once there is anything to confirm - from OCR or from the user typing.
  const hasRead =
    Object.values(panel).some((v) => String(v).trim() !== '') || ingredients.trim() !== ''

  // The confirmation fields are gated on this rather than on hasRead alone, so
  // they can still be revealed by hand when a photo yields nothing readable.
  // A finished extraction always unlocks them too: the note may tell the user
  // to type the list in, so the textarea must actually be on screen.
  const showFields = hasRead || extracting || manualEntry || Boolean(extractNote)

  return (
    <section className="mx-5 border border-rule bg-surface px-5 py-6">
      {/* ---------- 01 The claim ---------- */}
      <Marker n="01">
        {selected.length > 1 ? `The claims (${selected.length})` : 'The claim'}
      </Marker>

      <label htmlFor="claim-input" className="sr-only">
        Claims to check
      </label>
      <input
        id="claim-input"
        type="text"
        value={claim}
        onChange={(e) => onClaimChange(e.target.value)}
        placeholder="e.g., No Added Sugar, High Protein…"
        autoComplete="off"
        className="field mt-4 h-14 px-4 text-[16px]"
      />

      <p className="t-label mt-2.5 text-ink-faint">
        Separate multiple claims with a comma
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {chips.map((chip) => {
          const value = typeof chip === 'string' ? chip : chip.display_name
          const active = selectedSet.has(String(value).toLowerCase())
          return (
            <button
              key={value}
              type="button"
              onClick={() => toggleChip(value)}
              aria-pressed={active}
              className={`t-label rounded-[3px] border px-2.5 py-2 transition-colors ${
                active
                  ? 'border-ink bg-ink text-paper'
                  : 'border-rule text-ink-soft hover:border-ink-faint hover:text-ink'
              }`}
            >
              {active ? `${value} ×` : value}
            </button>
          )
        })}
      </div>

      {/* Solid vs liquid chooses which FSSAI threshold applies. */}
      <div className="mt-5 flex items-center justify-between border-t border-rule-soft pt-4">
        <span className="t-label text-ink-faint">Product form</span>
        <div className="flex items-center gap-1">
          {[
            { id: 'solid', label: 'Solid' },
            { id: 'liquid', label: 'Liquid' },
          ].map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => onFormChange(option.id)}
              aria-pressed={form === option.id}
              className={`t-label rounded-[3px] border px-3 py-2 transition-colors ${
                form === option.id
                  ? 'border-ink bg-ink text-paper'
                  : 'border-rule text-ink-faint hover:text-ink'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* Optional, and only shown if the dataset supplied categories. It sharpens
          the similar-product ranking and the solid/liquid guess - it never
          changes whether a claim passes. */}
      {categories.length > 0 && (
        <div className="mt-4 flex items-center justify-between gap-3">
          <label htmlFor="category-select" className="t-label shrink-0 text-ink-faint">
            Category
          </label>
          <select
            id="category-select"
            value={category}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="field h-11 max-w-[62%] px-2.5 text-[13.5px]"
          >
            <option value="">Optional — infer it</option>
            {categories.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* ---------- 02 The scans ---------- */}
      <Marker n="02" className="mt-8">
        Photograph the pack
      </Marker>

      <div className="mt-4 space-y-2.5">
        {SCAN_SLOTS.map((slot, index) => (
          <ScanSlot
            key={slot.id}
            index={index + 1}
            slot={slot}
            scan={scans[slot.id]}
            busy={extracting}
            onScan={(file) => onScan(slot.id, file)}
            onClear={() => onClearScan(slot.id)}
          />
        ))}
      </div>

      {/* Escape hatch: a blurry photo or no label at all should not dead-end the
          user, since the fields below are the real input either way. */}
      {!hasRead && !extracting && (
        <button
          type="button"
          onClick={() => setManualEntry((prev) => !prev)}
          className="t-label mt-3 text-ink-faint underline decoration-rule underline-offset-4 transition-colors hover:text-ink"
        >
          {manualEntry ? 'Hide manual entry' : 'No label handy? Enter values manually'}
        </button>
      )}

      {extracting && (
        <p className="t-label mt-4 flex items-center gap-2.5 text-ochre">
          <Spinner />
          Reading the label…
        </p>
      )}

      {extractNote && !extracting && (
        <p className="mt-4 border-l-2 border-rule pl-3 text-[13.5px] leading-relaxed text-ink-soft">
          {extractNote}
        </p>
      )}

      {/* ---------- 03 Confirm ---------- */}
      {showFields && (
        <>
          <Marker n="03" className="mt-8">
            Confirm the figures
          </Marker>

          <p className="mt-3 text-[13.5px] leading-relaxed text-ink-faint">
            Photographs are imperfect. Correct anything we misread — the verdict is only as sound as
            these numbers.
          </p>

          <div className="mt-5 grid grid-cols-2 gap-x-3 gap-y-4">
            {PANEL_FIELDS.map((field) => (
              <label key={field.key} className="block">
                <span className="t-label mb-1.5 block text-ink-faint">
                  {field.label}
                  <span className="ml-1 normal-case tracking-normal">({field.unit})</span>
                </span>
                <input
                  type="number"
                  inputMode="decimal"
                  step="any"
                  value={panel[field.key] ?? ''}
                  onChange={(e) => onPanelChange(field.key, e.target.value)}
                  placeholder="—"
                  className="field h-12 px-3 text-[15px] tabular-nums"
                />
              </label>
            ))}
          </div>

          <label className="mt-5 block">
            <span className="t-label mb-1.5 block text-ink-faint">Ingredients</span>
            <textarea
              rows={3}
              value={ingredients}
              onChange={(e) => onIngredientsChange(e.target.value)}
              placeholder="e.g., Multigrain (85.2%), Apple Juice Concentrate, Antioxidant (INS 306)"
              className="field resize-y px-3 py-2.5 text-[14.5px] leading-relaxed"
            />
          </label>
        </>
      )}

      {error && (
        <p
          role="alert"
          className="mt-5 border-l-2 border-vermilion py-1 pl-3 text-[13.5px] leading-relaxed text-vermilion-deep"
        >
          {error}
        </p>
      )}

      {/* ---------- Verify ---------- */}
      <button
        type="button"
        onClick={onVerify}
        disabled={!canVerify}
        className="btn-primary mt-7 flex h-14 w-full items-center justify-center gap-3 rounded-tile"
      >
        {verifying ? (
          <>
            <Spinner light />
            {selected.length > 1
              ? `Checking ${selected.length} claims`
              : 'Checking against FSSAI rules'}
          </>
        ) : selected.length > 1 ? (
          `Verify ${selected.length} claims`
        ) : (
          'Verify claim'
        )}
      </button>

      <div className="mt-4 flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={onReset}
          className="t-label text-ink-faint underline decoration-rule underline-offset-4 transition-colors hover:text-ink"
        >
          Start over
        </button>
        {ocrAvailable === false && (
          <>
            <span aria-hidden="true" className="h-3 w-px bg-rule" />
            <span className="t-label text-ink-faint">No camera reading on this server</span>
          </>
        )}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */

function ScanSlot({ index, slot, scan, busy, onScan, onClear }) {
  const cameraRef = useRef(null)
  const uploadRef = useRef(null)
  const captured = Boolean(scan)

  return (
    <div className="scan-slot p-3" data-state={captured ? 'captured' : 'pending'}>
      <div className="flex items-center gap-3.5">
        {captured ? (
          <img
            src={scan.url}
            alt={`${slot.title} preview`}
            className="size-13 shrink-0 rounded-[4px] object-cover"
          />
        ) : (
          <span className="grid size-13 shrink-0 place-items-center rounded-[4px] bg-paper-deep font-display text-[15px] italic text-ink-faint">
            {index}
          </span>
        )}

        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] text-ink">{slot.title}</p>
          <p className="t-label mt-1 truncate text-ink-faint">
            {captured ? 'Captured — check it is readable' : slot.hint}
          </p>
        </div>

        {captured && (
          <button
            type="button"
            onClick={onClear}
            aria-label={`Remove ${slot.title}`}
            className="grid size-11 shrink-0 place-items-center rounded-[3px] text-ink-faint transition-colors hover:text-vermilion"
          >
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>

      {/* Phones must be able to choose: the camera input forces the camera,
          while the plain file input opens the gallery / file browser. */}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => cameraRef.current?.click()}
          disabled={busy}
          className={`t-label flex h-11 flex-1 items-center justify-center gap-2 rounded-[3px] border transition-colors disabled:opacity-40 ${
            captured
              ? 'border-rule text-ink-soft hover:border-ink'
              : 'border-ink bg-ink text-paper'
          }`}
        >
          <CameraIcon />
          {captured ? 'Retake' : 'Take photo'}
        </button>
        <button
          type="button"
          onClick={() => uploadRef.current?.click()}
          disabled={busy}
          className="t-label flex h-11 flex-1 items-center justify-center gap-2 rounded-[3px] border border-rule text-ink-soft transition-colors hover:border-ink disabled:opacity-40"
        >
          <UploadIcon />
          Upload
        </button>
      </div>

      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onScan(file)
          // Reset so re-picking the same file still fires onChange.
          e.target.value = ''
        }}
      />
      <input
        ref={uploadRef}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onScan(file)
          // Reset so re-picking the same file still fires onChange.
          e.target.value = ''
        }}
      />
    </div>
  )
}

function CameraIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="size-4 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path
        d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="13" r="3.2" />
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="size-4 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M12 16V4m0 0 4 4m-4-4L8 8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" strokeLinecap="round" />
    </svg>
  )
}

/** Editorial section marker: numeral, label, then a rule to the margin. */
function Marker({ n, className = '', children }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <span className="font-display text-[15px] italic leading-none text-vermilion">{n}</span>
      <h2 className="t-label text-ink">{children}</h2>
      <span aria-hidden="true" className="h-px flex-1 bg-rule" />
    </div>
  )
}

function Spinner({ light = false }) {
  return (
    <span
      className={`size-3.5 animate-spin rounded-full border border-current border-t-transparent ${
        light ? 'opacity-90' : 'text-ochre'
      }`}
    />
  )
}
