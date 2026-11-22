import { verdictOf } from '../constants'

/**
 * The verdict card: one stamp, then the evidence behind it.
 * Everything shown here comes straight from the backend's Decision object.
 */
export default function ResultCard({ result }) {
  const decision = result?.decision || {}
  const verdict = verdictOf(decision)

  return (
    <section className="animate-rise mx-5 border border-rule bg-surface px-5 py-6">
      <header className="flex items-center justify-between gap-3">
        <span data-verdict={verdict.key} className="verdict-tag">
          {verdict.label}
        </span>
        {result?.llm_used && <span className="t-label text-ink-faint">Model-written summary</span>}
      </header>

      <h2 className="mt-5 font-figure text-[28px] font-normal italic leading-[1.12] text-ink">
        {verdict.headline}
      </h2>
      <p className="t-body mt-3 text-[14.5px]">{verdict.blurb}</p>

      {result?.claim_text && (
        <p className="mt-5 border-l-2 border-rule pl-3 text-[14px] leading-relaxed text-ink-soft">
          Claim checked —{' '}
          <span className="font-display text-[16px] italic text-ink">“{result.claim_text}”</span>
        </p>
      )}

      {decision.reason && (
        <Section title="Why">
          <p className="t-body text-[14.5px]">{decision.reason}</p>
        </Section>
      )}

      {decision.measured_value != null && decision.threshold != null && (
        <Section title="The figures">
          <div className="flex items-baseline gap-5 border-y border-rule py-4">
            <Figure label="Measured" value={decision.measured_value} unit={decision.unit} />
            <span className="font-display text-[20px] leading-none text-ink-faint">
              {comparatorSymbol(decision.comparator)}
            </span>
            <Figure label="Required" value={decision.threshold} unit={decision.unit} />
          </div>
        </Section>
      )}

      {decision.deceptive_flags?.length > 0 && (
        <Section title="Contradicted by the ingredients">
          <ul className="space-y-3">
            {decision.deceptive_flags.map((flag) => (
              <li key={flag} className="border-l-2 border-ochre pl-3">
                <p className="text-[15px] text-ink">{flag}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed text-ink-faint">
                  Present in the ingredient list despite the claim.
                </p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {decision.missing_fields?.length > 0 && (
        <Section title="Still needed">
          <p className="t-body text-[14px]">
            {decision.missing_fields.join(', ')} — add{' '}
            {decision.missing_fields.length === 1 ? 'this value' : 'these values'} above and check
            again.
          </p>
        </Section>
      )}

      {result?.explanation && (
        <section className="mt-7">
          <div className="flex items-center gap-3">
            <h3 className="font-display text-[22px] font-semibold leading-none text-ink">
              In plain words
            </h3>
            <span aria-hidden="true" className="h-px flex-1 bg-rule-soft" />
          </div>
          <PlainWords text={result.explanation} />
        </section>
      )}

      {decision.warnings?.length > 0 && (
        <Section title="Worth knowing">
          <ul className="space-y-2">
            {decision.warnings.map((warning) => (
              <li key={warning} className="pl-4 text-[13px] leading-relaxed text-ink-faint">
                — {warning}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {result?.similar_products?.length > 0 && (
        <Section title="Similar packs in the dataset">
          <ul className="divide-y divide-rule border-t border-rule">
            {result.similar_products.slice(0, 3).map((product, index) => (
              <li key={product.id ?? index} className="py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[15px] text-ink">{product.product_name}</span>
                  {product.severity_level && (
                    <span className="t-label shrink-0 text-ink-faint">
                      {product.severity_level}
                    </span>
                  )}
                </div>
                {product.front_claim && (
                  <p className="t-label mt-1.5 text-ink-faint">Claim — {product.front_claim}</p>
                )}
                {product.deceptive_mechanism && (
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
                    {product.deceptive_mechanism}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <p className="mt-7 border-t border-rule pt-4 text-[11.5px] leading-relaxed text-ink-faint">
        An informational check against a Phase-1 subset of FSSAI labelling rules. Not legal or
        medical advice.
      </p>
    </section>
  )
}

/* ------------------------------------------------------------------ */

function Section({ title, children }) {
  return (
    <section className="mt-7">
      <div className="flex items-center gap-3">
        <h3 className="t-label text-ink">{title}</h3>
        <span aria-hidden="true" className="h-px flex-1 bg-rule-soft" />
      </div>
      <div className="mt-3.5">{children}</div>
    </section>
  )
}

function Figure({ label, value, unit }) {
  return (
    <div>
      <p className="t-label text-ink-faint">{label}</p>
      <p className="mt-1.5 font-figure text-[30px] leading-none text-ink">
        {value}
        {unit ? <span className="ml-1.5 font-body text-[13px] text-ink-faint">{unit}</span> : null}
      </p>
    </div>
  )
}

const HEADING_MAP = [
  ['the gist', 'The gist', 'gist'],
  ['why it landed this way', 'Why it landed this way', 'why'],
  ['watch out', 'Watch out', 'alert'],
  ['the loophole', 'Watch out', 'alert'],
  ['loophole', 'Watch out', 'alert'],
  ['verdict', 'The gist', 'gist'],
  ['why (rule applied)', 'Why it landed this way', 'why'],
  ['why', 'Why it landed this way', 'why'],
]

function PlainWords({ text }) {
  const sections = parsePlainWords(text)
  if (sections.length === 0) return null

  return (
    <ol className="mt-4 overflow-hidden rounded-card border border-rule">
      {sections.map((section, index) => (
        <li
          key={`${section.title}-${index}`}
          className={`border-b border-rule px-4 py-4 last:border-b-0 ${
            section.tone === 'alert' ? 'bg-[#f8f1e6]' : 'bg-paper-deep'
          }`}
        >
          <div className="flex items-baseline justify-between gap-3">
            <h4 className="font-display text-[22px] font-bold leading-tight text-ink">
              {section.title}
            </h4>
            <span className="t-label shrink-0 text-ink-faint">
              {String(index + 1).padStart(2, '0')}
            </span>
          </div>
          {section.paragraphs.map((paragraph) => (
            <p key={paragraph} className="t-body mt-3 text-[14.5px] leading-[1.72]">
              {paragraph}
            </p>
          ))}
        </li>
      ))}
    </ol>
  )
}

function parsePlainWords(text) {
  const keys = HEADING_MAP.map(([key]) => escapeRegExp(key)).join('|')
  let source = String(text || '')
    .replace(/\r\n/g, '\n')
    .replace(/\*\*/g, '')
    .replace(/__/g, '')
    .replace(/^#+\s*/gm, '')
    .replace(/^\d+[.)]\s+/gm, '')
    .replace(new RegExp(`\\s+(${keys})\\s*:\\s*`, 'gi'), '\n$1\n')
    .replace(new RegExp(`^(${keys})\\s*:\\s*`, 'gim'), '$1\n')
    .trim()
  if (!source) return []

  const sections = []
  let current = null

  const flush = () => {
    if (!current) return
    const paragraphs = splitParagraphs(current.buf.join('\n'))
    if (paragraphs.length > 0) {
      sections.push({ title: current.title, tone: current.tone, paragraphs })
    }
    current = null
  }

  for (const raw of source.split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('(LLM unavailable')) continue
    const mapped = mapHeading(line)
    if (mapped) {
      flush()
      current = { ...mapped, buf: [] }
      continue
    }
    if (!current) current = { title: 'The gist', tone: 'gist', buf: [] }
    current.buf.push(line)
  }
  flush()
  return sections
}

function mapHeading(raw) {
  const key = String(raw || '')
    .replace(/:$/, '')
    .trim()
    .toLowerCase()
  const match = HEADING_MAP.find(([alias]) => alias === key)
  return match ? { title: match[1], tone: match[2] } : null
}

function splitParagraphs(body) {
  const chunks = String(body)
    .split(/\n{2,}/)
    .map((chunk) => chunk.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
  if (chunks.length > 1) return chunks

  const sentences = (chunks[0] || '').match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [body]
  const cleaned = sentences.map((s) => s.trim()).filter(Boolean)
  const paragraphs = []
  for (let i = 0; i < cleaned.length; i += 2) {
    paragraphs.push(cleaned.slice(i, i + 2).join(' '))
  }
  return paragraphs.filter(Boolean)
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function comparatorSymbol(comparator) {
  if (comparator === 'lte') return '≤'
  if (comparator === 'lt') return '<'
  if (comparator === 'gte') return '≥'
  if (comparator === 'gt') return '>'
  return 'vs'
}
