import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { extractLabel, getCategories, getClaims, getHealth, verifyClaim } from './api'
import { HISTORY_KEY, HISTORY_LIMIT, PANEL_FIELDS } from './constants'
import { prepareImageForUpload } from './image'
import Hero from './components/Hero'
import TopNav from './components/TopNav'
import VerifyCard, { splitClaims } from './components/VerifyCard'
import ResultCard from './components/ResultCard'
import ResearchCallout from './components/ResearchCallout'
import Footer from './components/Footer'
import { HelpModal, HistoryDrawer, PaperModal } from './components/Overlays'

/** Empty editable panel, so every field starts controlled. */
const blankPanel = () => Object.fromEntries(PANEL_FIELDS.map((f) => [f.key, '']))

export default function App() {
  // --- backend capabilities -------------------------------------------------
  const [health, setHealth] = useState(null)
  const [claims, setClaims] = useState([])
  const [categories, setCategories] = useState([])

  // --- inputs ---------------------------------------------------------------
  const [claim, setClaim] = useState('')
  const [form, setForm] = useState('solid')
  // Optional. Helps infer solid/liquid and ranks similar products.
  const [category, setCategory] = useState('')
  // scans: { ingredients: {file, url}, panel: {file, url} }
  const [scans, setScans] = useState({ ingredients: null, panel: null })

  // --- extraction (step 1: what did we read?) -------------------------------
  const [extracting, setExtracting] = useState(false)
  const [extractNote, setExtractNote] = useState(null)
  const [panel, setPanel] = useState(blankPanel)
  const [ingredients, setIngredients] = useState('')
  const [labelText, setLabelText] = useState('')

  // --- verdict (step 2) -----------------------------------------------------
  const [verifying, setVerifying] = useState(false)
  // One entry per comma-separated claim the user asked about.
  const [results, setResults] = useState([])
  const [error, setError] = useState(null)

  // --- overlays + history ---------------------------------------------------
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [paperOpen, setPaperOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [history, setHistory] = useState([])

  const resultRef = useRef(null)
  // Guards against a slow first OCR overwriting a newer result: adding photo 1
  // and then photo 2 can start two extractions, and the older one may finish
  // last. Only the latest request is allowed to write to the fields.
  const extractSeq = useRef(0)

  // -------------------------------------------------------------------------
  // Capabilities + saved history, once on mount.
  // -------------------------------------------------------------------------
  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null))
    getClaims()
      .then((data) => setClaims(data.claims || []))
      .catch(() => setClaims([]))
    getCategories()
      .then((data) => setCategories(data.categories || []))
      .catch(() => setCategories([]))

    try {
      const raw = window.localStorage.getItem(HISTORY_KEY)
      if (raw) setHistory(JSON.parse(raw))
    } catch {
      // Corrupt or unavailable storage is not worth breaking the app over.
    }
  }, [])

  // Keep the latest scans reachable from the unmount cleanup without making
  // that cleanup run on every scan change (which would revoke URLs still in use).
  const scansRef = useRef(scans)
  scansRef.current = scans

  // Release the thumbnail object URLs, but only when the app unmounts.
  useEffect(
    () => () => {
      Object.values(scansRef.current).forEach(
        (scan) => scan?.url && URL.revokeObjectURL(scan.url),
      )
    },
    [],
  )

  // -------------------------------------------------------------------------
  // Scanning
  // -------------------------------------------------------------------------
  const runExtract = useCallback(async (nextScans) => {
    const seq = ++extractSeq.current
    setExtracting(true)
    setExtractNote(null)
    setError(null)
    try {
      // Phones hand us 8-12 MP photos. Downscale and apply EXIF rotation before
      // uploading, or the request can exceed the body limit and OCR stalls.
      // Sequential, because decoding two large photos at once is heavy on
      // low-memory phones.
      const ingredientsFile = await prepareImageForUpload(nextScans.ingredients?.file)
      const panelFile = await prepareImageForUpload(nextScans.panel?.file)

      const data = await extractLabel({ ingredientsFile, panelFile })
      // A newer scan superseded this request while it was in flight.
      if (seq !== extractSeq.current) return

      // Seed the editable fields with whatever OCR found. Only touch the panel
      // when a panel photo was actually sent: an ingredient-only pass must not
      // erase numbers the user has already typed.
      if (nextScans.panel?.file) {
        setPanel({ ...blankPanel(), ...stringify(data.parsed_panel || {}) })
      }
      setIngredients(data.ingredients || '')
      setLabelText(data.extracted_text || '')

      const rows = Object.keys(data.parsed_panel || {}).length
      const gotIngredients = Boolean(String(data.ingredients || '').trim())
      const hasPanelPhoto = Boolean(nextScans.panel?.file)

      if (rows > 0) {
        setExtractNote(
          `Read ${rows} value${rows === 1 ? '' : 's'} from your label. Please check them below.`,
        )
      } else if (!hasPanelPhoto) {
        // Only the ingredient photo has been taken so far. Never imply the
        // nutrition table was read when it was not even uploaded.
        setExtractNote(
          gotIngredients
            ? 'Ingredient list read. Now add the nutrition value table.'
            : 'We could not read the ingredient list. Try a clearer photo or type it in below.',
        )
      } else {
        setExtractNote(
          gotIngredients
            ? 'We read the ingredient list but could not read the nutrition numbers. Enter them below to continue.'
            : 'We could not read any nutrition numbers. Enter them below to continue.',
        )
      }
    } catch (err) {
      if (seq !== extractSeq.current) return
      if (err.status === 501) {
        setExtractNote(
          'Automatic reading is unavailable on this server. Enter the values below by hand.',
        )
      } else {
        setExtractNote(`Could not read the label: ${err.message}`)
      }
    } finally {
      if (seq === extractSeq.current) setExtracting(false)
    }
  }, [])

  const handleScan = useCallback(
    (slotId, file) => {
      if (!file) return
      // Read from the ref, not the render closure: two picks in quick
      // succession must not overwrite each other with stale state.
      const previous = scansRef.current
      // Replacing a photo should release the one it is replacing.
      if (previous[slotId]?.url) URL.revokeObjectURL(previous[slotId].url)
      const next = {
        ...previous,
        [slotId]: { file, url: URL.createObjectURL(file) },
      }
      scansRef.current = next
      setScans(next)
      setResults([])

      // Read as soon as the ingredient photo exists, so the ingredient list is
      // visible (and editable) even before the nutrition table is added. When
      // the second photo arrives this runs again and fills the numbers too.
      if (next.ingredients?.file) runExtract(next)
    },
    [runExtract],
  )

  const clearScan = useCallback(
    (slotId) => {
      // A result for the photo we are removing must not arrive later and fill
      // the fields back in.
      extractSeq.current += 1
      setExtracting(false)
      const previous = scansRef.current
      if (previous[slotId]?.url) URL.revokeObjectURL(previous[slotId].url)
      const next = { ...previous, [slotId]: null }
      scansRef.current = next
      setScans(next)
      setResults([])
      setExtractNote(null)
    },
    [],
  )

  // -------------------------------------------------------------------------
  // Verifying
  // -------------------------------------------------------------------------
  const canVerify = useMemo(() => {
    const hasReadSomething =
      Object.values(panel).some((v) => String(v).trim() !== '') || ingredients.trim() !== ''
    return (
      splitClaims(claim).length > 0 && hasReadSomething && !verifying && !extracting
    )
  }, [claim, panel, ingredients, verifying, extracting])

  const handleVerify = useCallback(async () => {
    const claimsToCheck = splitClaims(claim)
    if (claimsToCheck.length === 0) return

    setVerifying(true)
    setError(null)

    // Send numbers as floats, drop blanks, and pass the raw text so the
    // backend can still check for the mandatory disclaimer wording.
    const numericPanel = {}
    for (const { key } of PANEL_FIELDS) {
      const raw = String(panel[key] ?? '').trim()
      if (raw === '') continue
      const num = Number(raw)
      if (!Number.isNaN(num)) numericPanel[key] = num
    }

    const common = {
      form,
      // Only send it when chosen, so the backend's own inference still applies.
      category: category || undefined,
      panel: numericPanel,
      ingredients,
      label_text: labelText,
      use_llm: true,
    }

    try {
      // The backend decides one claim per request, so fan out in parallel and
      // keep the results in the order the user typed them.
      const settled = await Promise.allSettled(
        claimsToCheck.map((value) => verifyClaim({ ...common, claim: value })),
      )

      const fulfilled = settled
        .filter((outcome) => outcome.status === 'fulfilled')
        .map((outcome) => outcome.value)
      const failed = settled.filter((outcome) => outcome.status === 'rejected')

      if (fulfilled.length > 0) {
        setResults(fulfilled)
        fulfilled.forEach(pushHistory)
        // Give the cards a moment to mount, then bring them into view.
        window.setTimeout(
          () => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
          80,
        )
      }

      if (failed.length > 0) {
        const first = failed[0].reason?.message || 'Something went wrong.'
        setError(
          failed.length === claimsToCheck.length
            ? first
            : `${failed.length} of ${claimsToCheck.length} claims could not be checked — ${first}`,
        )
      }
    } finally {
      setVerifying(false)
    }
  }, [claim, form, category, panel, ingredients, labelText])

  const pushHistory = (data) => {
    const entry = {
      // Several claims are verified in the same tick, so Date.now() alone
      // would produce colliding keys.
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      at: new Date().toISOString(),
      claim: data.claim_text,
      status: data.decision?.status,
      compliant: data.decision?.is_technically_compliant,
      deceptive: data.decision?.is_deceptive,
    }
    setHistory((prev) => {
      const next = [entry, ...prev].slice(0, HISTORY_LIMIT)
      try {
        window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
      } catch {
        // Private-browsing mode - history just will not persist.
      }
      return next
    })
  }

  const handleReset = useCallback(() => {
    extractSeq.current += 1
    setExtracting(false)
    Object.values(scans).forEach((scan) => scan?.url && URL.revokeObjectURL(scan.url))
    const cleared = { ingredients: null, panel: null }
    scansRef.current = cleared
    setScans(cleared)
    setClaim('')
    setCategory('')
    setPanel(blankPanel())
    setIngredients('')
    setLabelText('')
    setResults([])
    setError(null)
    setExtractNote(null)
  }, [scans])

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className="app-shell">
      <TopNav
        onOpenMenu={() => setDrawerOpen(true)}
        onOpenHistory={() => setHistoryOpen(true)}
        onOpenHelp={() => setHelpOpen(true)}
      />

      <main className="pb-2">
        <Hero />
        <VerifyCard
          claim={claim}
          onClaimChange={setClaim}
          claims={claims}
          form={form}
          onFormChange={setForm}
          categories={categories}
          category={category}
          onCategoryChange={setCategory}
          scans={scans}
          onScan={handleScan}
          onClearScan={clearScan}
          extracting={extracting}
          extractNote={extractNote}
          panel={panel}
          onPanelChange={(key, value) => setPanel((prev) => ({ ...prev, [key]: value }))}
          ingredients={ingredients}
          onIngredientsChange={setIngredients}
          canVerify={canVerify}
          verifying={verifying}
          onVerify={handleVerify}
          onReset={handleReset}
          error={error}
          ocrAvailable={health?.ocr_available}
        />
        {results.length > 0 && (
          <div ref={resultRef} className="mt-4 space-y-4 scroll-mt-2">
            {results.map((item, index) => (
              <ResultCard key={`${item.claim_text}-${index}`} result={item} />
            ))}
          </div>
        )}
        <ResearchCallout onOpenPaper={() => setPaperOpen(true)} />
      </main>

      <Footer />

      <Overlays
        drawerOpen={drawerOpen}
        onCloseDrawer={() => setDrawerOpen(false)}
        onOpenHelp={() => {
          setDrawerOpen(false)
          setHelpOpen(true)
        }}
        onOpenPaper={() => {
          setDrawerOpen(false)
          setPaperOpen(true)
        }}
        helpOpen={helpOpen}
        onCloseHelp={() => setHelpOpen(false)}
        paperOpen={paperOpen}
        onClosePaper={() => setPaperOpen(false)}
        historyOpen={historyOpen}
        onCloseHistory={() => setHistoryOpen(false)}
        history={history}
        health={health}
      />
    </div>
  )
}

/** Turn {protein_g: 11.5} into {protein_g: '11.5'} for controlled inputs. */
function stringify(parsed) {
  return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]))
}

/** Groups the three overlay surfaces so App's JSX stays readable. */
function Overlays({
  drawerOpen,
  onCloseDrawer,
  onOpenHelp,
  onOpenPaper,
  helpOpen,
  onCloseHelp,
  paperOpen,
  onClosePaper,
  historyOpen,
  onCloseHistory,
  history,
  health,
}) {
  return (
    <>
      <NavDrawer
        open={drawerOpen}
        onClose={onCloseDrawer}
        onOpenHelp={onOpenHelp}
        onOpenPaper={onOpenPaper}
      />
      <HelpModal open={helpOpen} onClose={onCloseHelp} health={health} />
      <PaperModal open={paperOpen} onClose={onClosePaper} />
      <HistoryDrawer open={historyOpen} onClose={onCloseHistory} history={history} />
    </>
  )
}

/** The slide-out navigation drawer opened by the hamburger. */
function NavDrawer({ open, onClose, onOpenHelp, onOpenPaper }) {
  const links = [
    { label: 'Home', action: onClose, hint: 'Back to the top' },
    { label: 'How It Works', action: onOpenHelp, hint: 'The seven-step check' },
    { label: 'About the Research', action: onOpenPaper, hint: 'Read the survey paper' },
  ]

  return (
    <div
      className={`fixed inset-0 z-50 ${open ? '' : 'pointer-events-none'}`}
      aria-hidden={!open}
    >
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-ink/35 transition-opacity duration-300 ${
          open ? 'opacity-100' : 'opacity-0'
        }`}
      />
      <nav
        className={`absolute left-0 top-0 flex h-full w-[80%] max-w-[320px] flex-col border-r border-rule bg-paper transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-rule px-6 py-6">
          <div>
            <p className="font-display text-[22px] italic leading-tight text-ink">Menu</p>
            <p className="t-label mt-2 text-ink-faint">URE — Food Label Analyser</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="grid size-11 shrink-0 place-items-center rounded-tile text-ink-faint transition-colors hover:bg-paper-deep hover:text-ink"
          >
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <ul className="px-6 py-5">
          {links.map((link) => (
            <li key={link.label} className="border-b border-rule-soft last:border-b-0">
              <button
                type="button"
                onClick={link.action}
                className="flex w-full flex-col items-start py-4 text-left"
              >
                <span className="text-[16px] text-ink">{link.label}</span>
                <span className="t-label mt-1.5 text-ink-faint">{link.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
