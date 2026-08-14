# Lecturer

Lecturer turns a monograph into an audiobook that sounds like the author lecturing from his own
book. It takes an EPUB or PDF, extracts the running text and its footnotes, reworks that into a
script of utterances tagged with a delivery manner, and speaks it.

The hard part is the apparatus. A scholarly monograph is not prose with decorations on it — the
footnotes, the citation sigla, and the bibliography carry a large share of the argument, and none
of them survive being read aloud verbatim. Lecturer treats each of those as its own problem:
substantive notes are respoken as digressions that flow with the text, bare citations are dropped,
and inline citations are spoken the way a lecturer would say them ("1 Cor 2:10" becomes "First
Corinthians two, ten") rather than left for a TTS engine to mangle.

## What it does today

- **Extraction** from EPUB and PDF into per-section text with anchored footnotes. Chapter
  splitting reads the book's own navigation tree rather than file order; page references read the
  PDF's own embedded page labels rather than raw position, so a locator names the page a reader
  would actually see printed. Bibliographies are recovered by left-margin geometry where the PDF's
  own block detector glues hanging-indent entries together.
- **Redaction** — ordered layers reworking extraction into a script: seam mending across page
  breaks, footnote weaving, citation dictation, writing-system tagging, and breath pointing for
  overlong comma-free stretches.
- **Recitation** through Kokoro-82M, roughly 4× realtime on CPU, chunked at sentence boundaries
  under the model's phoneme batch limit. Per-document pronunciation lexicon applied at phoneme
  level, with per-section signatures so editing one entry re-renders only the sections that use it.
- **Publishing** to per-section Opus with an M3U playlist, plus a single chaptered `.m4b` where
  ffmpeg is available. Tags are read from the source document's own metadata, and left empty rather
  than guessed where the document doesn't state a field plainly.

Three weaving variants fork the output tree and live side by side: `book` (notes dropped),
`glossed` (notes respoken as asides via an LLM), and `verbatim` (every note at its anchor, for
inspection).

## Where the LLM sits, and where it doesn't

The design constraint throughout is that a language model is allowed to do work whose output can be
checked, and nothing else.

- Its expansions are **narrowed until they're verifiable**. `draft-classical` doesn't ask a model
  who wrote a work; the author is already confirmed from the document's own footnotes, and the only
  ask is turning a settled author-and-siglum pair into a spoken title.
- Its results become **hand-editable artefacts**, not runtime behaviour. Drafted sigla land in a
  TOML canon — per-document tier, promoted additively into a shared tier — that deterministic code
  then consumes. A human edit is never overwritten; only an unresolved stub is.
- Where it does generate prose, it's **guarded**. The glossator must return the paragraph's body
  text verbatim and in full; a paragraph that fails the check falls back to the deterministic
  verbatim weave rather than shipping something plausible.
- Where the evidence is genuinely ambiguous, it **abstains and says where to look**. A siglum
  paired with two authors is reported, not resolved. An unconfirmed bibliography house style
  abstains every entry to raw text rather than mis-parsing a shape the project hasn't been tested
  against. Citation review writes a per-document report of spans that look like citations but
  didn't convert, with enough surrounding context to read the cause off the text.

The practical result is output you can diff between runs, hold to a regression suite, and hand to
someone who has to trust it without reading the source.

## Who it's for

A reader who cannot see the page and does not use a computer. The interface is a command line with
a small number of verbs, which is awkward for a sighted novice and entirely workable for a
sight-impaired user on a braille terminal.

## Usage

```
lecturer -o eros_magic "texts/Ioan P. Couliano - Eros and Magic in the Renaissance.epub"
```

This creates `./eros_magic/`, copies the document in, links `working_text` to the copy, and
extracts the text into `./eros_magic/sections/` — one file per section, with a matching
`.footnotes.txt` beside it. Every later artefact lands in the same directory.

The phases are verbs — `extract`, `redact`, `recite`, `publish`, plus `draft-lexicon` and
`draft-classical`/`promote-classical` for the canon. Verbs resolve their own dependencies; glossing
never runs implicitly.

## State

Working and verified against real corpora, not synthetic fixtures. Extraction, redaction, and
recitation run end to end; several books have been taken all the way to a tagged `.m4b`.

Known gaps, all deliberate rather than undiscovered:

- Scanned PDFs with no text layer, no outline, and no font-size profile have no extractor path.
  Upstream layout tools have been evaluated and a candidate chosen; it isn't wired in.
- The bibliography heading pattern is English-only, so a non-English heading yields a correct
  section but no parsed structure.
- Bekker numbering and Diels-Kranz are further closed citation systems of the same shape as the
  implemented ones, waiting on a forcing case.

`docs/` carries the design notes; `CLAUDE.md` carries the full architecture, including why each
of the above is where it is.

## Development

Requires [uv](https://docs.astral.sh/uv/), [just](https://just.systems/), and optionally
[direnv](https://direnv.net/).

```
just setup   # install dependencies and commit hooks
just         # list the other recipes
```

Source monographs live in `texts/`, which is gitignored — the corpus is copyrighted.

## Licence

ISC.

______________________________________________________________________

> *For my father, who could bend beams with his mind and poked me with a sharp stick until I was good at mathematics.*
