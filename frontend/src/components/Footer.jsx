/** Grounded, minimal footer. */
export default function Footer() {
  return (
    <footer className="mt-8 border-t border-rule px-6 py-8">
      <p className="text-[15px] text-ink">URE — Food Label Analyser</p>

      <p className="mt-3 text-[12.5px] leading-relaxed text-ink-soft">
        A Phase-1 academic project. Claims are held against a subset of FSSAI labelling rules and a
        curated dataset of Indian packaged foods. Nutrition values are read from the photographs you
        provide and can be corrected by you.
      </p>

      <p className="mt-4 text-[11.5px] leading-relaxed text-ink-faint">
        Informational only — not legal, medical or dietary advice. Always read the original pack.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-2">
        <a
          href="https://www.fssai.gov.in/"
          target="_blank"
          rel="noreferrer"
          className="t-label text-ink-faint underline decoration-rule underline-offset-4 transition-colors hover:text-ink"
        >
          FSSAI
        </a>
        <span aria-hidden="true" className="h-3 w-px bg-rule" />
        <a
          href="https://www.fssai.gov.in/cms/food-safety-and-standards-regulations.php"
          target="_blank"
          rel="noreferrer"
          className="t-label text-ink-faint underline decoration-rule underline-offset-4 transition-colors hover:text-ink"
        >
          Labelling regulations
        </a>
      </div>
    </footer>
  )
}
