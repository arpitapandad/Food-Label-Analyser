/**
 * Sticky masthead: hamburger on the left, two small-caps utilities on the right.
 * Flat paper with a single hairline — no blur, no glass.
 */
export default function TopNav({ onOpenMenu, onOpenHistory, onOpenHelp }) {
  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-paper">
      <div className="flex items-center justify-between pl-2 pr-3">
        <button
          type="button"
          onClick={onOpenMenu}
          aria-label="Open menu"
          className="grid size-12 place-items-center rounded-tile text-ink transition-colors hover:bg-paper-deep"
        >
          <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 7h18M3 12h18M3 17h12" strokeLinecap="round" />
          </svg>
        </button>

        <nav className="flex items-center">
          <button
            type="button"
            onClick={onOpenHistory}
            className="t-label h-12 px-3.5 text-ink-faint transition-colors hover:text-ink"
          >
            History
          </button>
          <span aria-hidden="true" className="h-3.5 w-px bg-rule" />
          <button
            type="button"
            onClick={onOpenHelp}
            className="t-label h-12 px-3.5 text-ink-faint transition-colors hover:text-ink"
          >
            Help
          </button>
        </nav>
      </div>
    </header>
  )
}
