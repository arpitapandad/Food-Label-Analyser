/** Secondary callout that opens the survey paper. */
export default function ResearchCallout({ onOpenPaper }) {
  return (
    <section className="mt-4 bg-ink px-6 py-7">
      <p className="t-label text-ochre">Behind the tool</p>

      <h2 className="mt-3 text-[24px] font-normal italic leading-[1.2] text-paper">
        How often do these claims actually mislead?
      </h2>

      <p className="mt-3 text-[14px] leading-[1.7] text-paper/60">
        The survey paper behind this project — what shoppers notice, what they miss, and how a
        health halo hides in the ingredient list.
      </p>

      <button
        type="button"
        onClick={onOpenPaper}
        className="t-label mt-6 flex h-13 w-full items-center justify-between border border-paper/25 px-4 text-paper transition-colors hover:border-paper/70"
      >
        Read my survey paper
        <svg
          viewBox="0 0 24 24"
          className="size-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </section>
  )
}
