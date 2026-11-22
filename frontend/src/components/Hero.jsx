/** The hero: one question set in the display cut, then the plain-language pitch. */
export default function Hero() {
  return (
    <section className="px-6 pb-7 pt-8">
      <h1 className="text-[34px] font-normal italic leading-[1.08] tracking-[-0.015em] text-ink">
        How true are claims made on the front of packaged foods?{' '}
        <span className="not-italic text-vermilion">Try it out!</span>
      </h1>

      <p className="t-body mt-5">
        The pack says <span className="font-display text-[17px] italic">“High Protein”</span>,{' '}
        <span className="font-display text-[17px] italic">“No Added Sugar”</span>,{' '}
        <span className="font-display text-[17px] italic">“Heart Healthy”</span>. Scan the
        ingredient list and the nutrition table, and we will hold the claim against what the back of
        the pack actually says.
      </p>
    </section>
  )
}
