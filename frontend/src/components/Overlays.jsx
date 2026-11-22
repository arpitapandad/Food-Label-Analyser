import { useEffect } from 'react'

import { verdictOf } from '../constants'

/**
 * The three overlay surfaces opened from the nav:
 *   HelpModal      - how the 7-step check works
 *   HistoryDrawer  - past checks saved in localStorage
 *   PaperModal     - preview of the survey paper PDF
 */

/** Verdict -> dot colour, matching the marks used on the result card. */
const DOT = {
  true: 'bg-moss',
  misleading: 'bg-ochre',
  false: 'bg-vermilion',
  unknown: 'bg-slate',
  incomplete: 'bg-slate',
}

/* --------------------------------------------------------------------------
   Shared shell: backdrop, escape-to-close, body scroll lock.
   -------------------------------------------------------------------------- */
function Backdrop({ open, onClose }) {
  return (
    <div
      onClick={onClose}
      aria-hidden="true"
      className={`absolute inset-0 bg-ink/35 transition-opacity duration-300 ${
        open ? 'opacity-100' : 'opacity-0'
      }`}
    />
  )
}

function CloseButton({ onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="grid size-11 shrink-0 place-items-center rounded-tile text-ink-faint transition-colors hover:bg-paper-deep hover:text-ink"
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
      </svg>
    </button>
  )
}

/** Bottom sheet used by Help and the paper preview. */
function Sheet({ open, onClose, title, subtitle, children }) {
  useEscapeAndLock(open, onClose)

  return (
    <div className={`fixed inset-0 z-50 ${open ? '' : 'pointer-events-none'}`} aria-hidden={!open}>
      <Backdrop open={open} onClose={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`absolute inset-x-0 bottom-0 mx-auto flex max-h-[88dvh] w-full max-w-[430px] flex-col rounded-t-[14px] border-t border-rule bg-paper transition-transform duration-300 ease-out ${
          open ? 'translate-y-0' : 'translate-y-full'
        }`}
      >
        <div className="flex items-start gap-3 px-6 pb-4 pt-6">
          <div className="flex-1">
            <h2 className="text-[23px] font-normal italic leading-tight text-ink">{title}</h2>
            {subtitle && <p className="t-label mt-2 text-ink-faint">{subtitle}</p>}
          </div>
          <CloseButton onClick={onClose} label="Close" />
        </div>
        <div className="overflow-y-auto px-6 pb-10">{children}</div>
      </div>
    </div>
  )
}

/** Escape-to-close + scroll lock, shared by the sheet and the drawer. */
function useEscapeAndLock(open, onClose) {
  useEffect(() => {
    if (!open) return undefined

    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [open, onClose])
}

/* --------------------------------------------------------------------------
   Help / How It Works
   -------------------------------------------------------------------------- */
const STEPS = [
  {
    title: 'Read the claim',
    body: 'Your words are matched to a canonical FSSAI claim, including common aliases like “no sugar added”.',
  },
  {
    title: 'Screen for prohibited wording',
    body: 'Wording that implies curing, treating or preventing disease — “cures”, “boosts immunity” — is rejected outright.',
  },
  {
    title: 'Pick the rule',
    body: 'Each claim maps to a rule: which nutrient matters, the threshold, the unit and how the comparison is made.',
  },
  {
    title: 'Check you have the numbers',
    body: 'If the nutrient the rule depends on is missing from the panel, the answer is “need more data” — never a guess.',
  },
  {
    title: 'Compare against the threshold',
    body: 'The measured value is held against the FSSAI limit for a solid or liquid product. This is the technical pass or fail.',
  },
  {
    title: 'Scan the ingredient list',
    body: 'Separately, the ingredients are checked for hallmarks that quietly contradict the claim — the health-halo loophole.',
  },
  {
    title: 'Combine into one verdict',
    body: 'Compliant but contradicted by an ingredient becomes “Misleading”. Both true is “True”. Failing the number is “False”.',
  },
]

export function HelpModal({ open, onClose, health }) {
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="How the check works"
      subtitle="Seven steps, no guessing"
    >
      <ol className="divide-y divide-rule border-t border-rule">
        {STEPS.map((step, index) => (
          <li key={step.title} className="flex gap-4 py-4">
            <span className="w-5 shrink-0 font-display text-[17px] italic leading-tight text-vermilion">
              {index + 1}
            </span>
            <div>
              <p className="text-[15px] text-ink">{step.title}</p>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-7 border border-rule bg-surface px-4 py-4">
        <p className="t-label text-ink-faint">This server</p>
        <dl className="mt-3 space-y-2.5">
          <StatusRow label="Text reading" ok={health?.ocr_available} detail={health?.ocr_engine} />
          <StatusRow label="Explanation model" ok={health?.llm_configured} detail={health?.llm_model} />
          <StatusRow label="Rule set" ok={Boolean(health?.rules_version)} detail={health?.rules_version} />
        </dl>
      </div>

      <p className="mt-5 text-[12.5px] leading-relaxed text-ink-faint">
        The model only writes the plain-language summary. It never decides whether a claim passes —
        that is done entirely by the deterministic rule engine.
      </p>
    </Sheet>
  )
}

function StatusRow({ label, ok, detail }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[13px] text-ink-soft">{label}</dt>
      <dd className="flex items-center gap-2 text-[12.5px] text-ink-faint">
        <span className={`size-1.5 rounded-full ${ok ? 'bg-moss' : 'bg-slate'}`} aria-hidden="true" />
        {ok ? 'ready' : 'unavailable'}
        {detail ? ` · ${detail}` : ''}
      </dd>
    </div>
  )
}

/* --------------------------------------------------------------------------
   History drawer (right side)
   -------------------------------------------------------------------------- */
export function HistoryDrawer({ open, onClose, history }) {
  useEscapeAndLock(open, onClose)

  return (
    <div className={`fixed inset-0 z-50 ${open ? '' : 'pointer-events-none'}`} aria-hidden={!open}>
      <Backdrop open={open} onClose={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Scan history"
        className={`absolute right-0 top-0 flex h-full w-[86%] max-w-[360px] flex-col border-l border-rule bg-paper transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-rule px-6 py-6">
          <div>
            <h2 className="text-[23px] font-normal italic leading-tight text-ink">Scan history</h2>
            <p className="t-label mt-2 text-ink-faint">Kept on this device</p>
          </div>
          <CloseButton onClick={onClose} label="Close history" />
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {history.length === 0 ? (
            <p className="border-y border-rule py-8 text-center text-[13px] leading-relaxed text-ink-faint">
              Nothing here yet. Verify a claim and it will be listed.
            </p>
          ) : (
            <ul className="divide-y divide-rule border-t border-rule">
              {history.map((entry) => {
                const verdict = verdictOf({
                  status: entry.status,
                  is_technically_compliant: entry.compliant,
                  is_deceptive: entry.deceptive,
                })
                return (
                  <li key={entry.id} className="flex items-start gap-3 py-3.5">
                    <span
                      aria-hidden="true"
                      className={`mt-2 size-1.5 shrink-0 rounded-full ${DOT[verdict.key] || 'bg-slate'}`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[15px] text-ink">{entry.claim}</p>
                      <p className="t-label mt-1.5 text-ink-faint">
                        {verdict.label} · {formatDate(entry.at)}
                      </p>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </aside>
    </div>
  )
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleString(undefined, {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

/* --------------------------------------------------------------------------
   Survey paper preview
   -------------------------------------------------------------------------- */
/**
 * Drop your PDF at `frontend/public/survey-paper.pdf` and it shows up here.
 * (`public/` files are served from the site root, so the path is `/survey-paper.pdf`.)
 */
const PAPER_URL = '/survey-paper.pdf'

export function PaperModal({ open, onClose }) {
  return (
    <Sheet open={open} onClose={onClose} title="Survey paper" subtitle="The research behind this tool">
      <div className="h-[56dvh] overflow-hidden border border-rule bg-surface">
        {/* Sheet keeps its children mounted while closed, so an <object> here
            would request the PDF on every page load - a 404 until the file
            exists. Mount it only while the modal is actually open. */}
        {open && (
          <object data={PAPER_URL} type="application/pdf" className="size-full">
            <div className="grid size-full place-items-center px-6 text-center">
              <div>
                <p className="text-[15px] text-ink">The paper could not be previewed</p>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
                  Your browser may block inline PDFs. Open it in a new tab instead.
                </p>
              </div>
            </div>
          </object>
        )}
      </div>

      <a
        href={PAPER_URL}
        target="_blank"
        rel="noreferrer"
        className="btn-primary mt-5 flex h-13 items-center justify-center rounded-tile"
      >
        Open in a new tab
      </a>
    </Sheet>
  )
}
