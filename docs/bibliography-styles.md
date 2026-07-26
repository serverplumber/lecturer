# Bibliography styles: a sparse catalog

`redaction/elocution/bibliography.py` parses one style at a time, each gated by its own
`sniff_style` (or, once a second style exists, whichever one's coverage clears first — see
`docs/elocution.md`'s note on `style_sniffer`). This file is not a build queue: it's
what to check a new bibliography against before assuming it needs a new parser, and what
to name the parser if it does. Entries move from *candidate* to *characterized* to *built*
only on real corpus evidence — nothing here is assumed from a style guide, per this
project's whole discipline around `sniff_style`.

Two explicit non-goals, so this list doesn't get read as more than it is:

- **No author→style or publisher→style lookup.** *Tree of Gnosis* and *Eros and Magic*
  share an author (Couliano) and both started as French originals, yet use two different
  bibliography conventions in their English editions — the discriminator looks like the
  *publisher's* own editorial process (University of Chicago Press restyles to house
  convention; HarperSanFrancisco, a trade press, apparently didn't), not the author's own
  habits. Useful as a prior for a human deciding what to sample next — never a runtime
  input. `sniff_style` reads the document's own text, every time.
- **Not a queue to work through top-to-bottom.** A style stays a one-line placeholder
  until a real corpus needs it. Building ahead of evidence is exactly what this project's
  "grep-gate before building" habit exists to prevent.

The axes below are the ones `bibliography.py` already models — a new style is described
in these terms, not a fresh taxonomy:

- first-author order: inverted ("Surname, First") vs. natural ("First Surname")
- year position: tail-bare ("Publisher, Year.") vs. tail-parenthetical
  ("(Place: Publisher, Year).") vs. head (author-date, breaks every end-anchored pattern
  the notes-style parser uses)
- same-author continuation marker: character + repeat count (already sniffed generically,
  not per-style — see `_LEADING_DASH_RUN`)
- title framing: quoted (article/chapter) vs. plain (book), and what the container/chapter
  clause looks like ("Pages X in Y", "In Y, edited by Z", ...)
- whether there's a separate bibliography at all, vs. full citations given only in notes

## Built

**Chicago/SBL notes-bibliography, tail-year.** Inverted first author, natural-order
subsequent authors, quoted article/chapter titles, year at the tail (bare or after a
"Publisher. Year." inconsistency this corpus itself has). Confirmed corpora: `temple_gates`
(Wendt), *Eros and Magic* (Couliano, trans. Margaret Cook, University of Chicago Press).

## Characterized, not yet built

**Working name: "Plon style"** (after Éditions Plon, the original French publisher).
Natural-order *first* author too — no inversion at all — year inside a
"(Place: Publisher, Year)." parenthetical rather than bare at the tail, continuation
marker a doubled ASCII hyphen ("--,"/"--:"). Confirmed corpus: *Tree of Gnosis* (Couliano,
trans. H. S. Wiesner and the author, HarperSanFrancisco — a revised translation of *Les
Gnoses Dualistes d'Occident*, Éditions Plon, 1990). `sniff_style` correctly abstains on
this corpus today rather than mis-parsing it; building this parser is the next real unit
of work once a second corpus needing it shows up (or once we decide one confirmed
corpus is enough to justify it).

## Candidates — watch for, don't assume

Unconfirmed against anything in this project's own corpus. Listed so a new book can be
checked against a name instead of being characterized from scratch each time.

- **Author-date (Harvard/APA-adjacent).** Year immediately after the author's name, no
  notes-based citation at all. `sniff_style`'s `head_year` signal already exists
  specifically to detect and reject this shape from the current parser — no dedicated
  parser built, since nothing in hand needs one yet.
- **MLA-style Works Cited.** "Author. *Title*. Publisher, Year." — no place of
  publication (modern MLA dropped it), different container punctuation
  ("Title." *Container*, vol. X, no. Y, Year, pp. Z).
- **German academic citation.** Often fully inline — "Author, *Title* (Place Year), page"
  — parenthesized place+year with no surrounding comma. Plausible given how much
  Patristics/Classics scholarship is translated from German; nothing in hand yet.
- **Italian academic style.** *I miti dei dualismi occidentali* (Couliano, in the original
  Italian) sits in `texts/` unexplored — extraction currently recovers 0 footnotes from it
  at all, so this is an extraction gap, not yet a characterized style. Worth another look
  once epub footnote recovery is checked against a non-English source.
- **Numbered/Vancouver-style.** A bare numbered reference list keyed to inline `[3]`-style
  markers rather than named-author locators — structurally bigger than a new parser, since
  `Elocutor`'s whole citation-recognition approach assumes a named siglum, not a number
  standing for someone else's name.
- **No separate bibliography — full citations in notes only, "Ibid."/"op. cit." shorthand
  for repeats.** Not really a bibliography style at all — the reference data lives
  somewhere else entirely, resolved by a stateful "most recently cited work" register
  (closer in shape to `docs/elocution.md`'s `internal_ref`, component 14, than to anything
  in `bibliography.py`). *Out of This World*'s single back-matter "Notes" chapter may turn
  out to be exactly this shape once endnotes-chapter recovery exists to even look.

## Corpus gaps currently blocking new samples

Not styles — the reason we don't have more style evidence yet.

- **Endnotes-chapter recovery** (`extraction/pdf.py` only handles per-page footnotes today):
  blocks both *Out of This World* (OCR-corrupted besides) and *Tree of Gnosis* (bibliography
  already segments; 0 footnotes recovered — endnote markers are bare digits, no separable
  Notes section detected). Would unblock two texts at once if built.
- **`.djvu` / `.azw3`**: no extractor exists for either format
  (`Eros and Magic` djvu duplicate, both *Dizionario* volumes).
- *I miti dei dualismi occidentali* (Italian epub): 0 footnotes recovered; unexplored
  whether that's a markup gap or a genuine absence.
- `10.2307@30126650.pdf`: a short journal article, not a monograph — out of scope for this
  pipeline regardless of format support.
