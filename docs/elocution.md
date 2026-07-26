## Elocution : Hold the alphabet soup

A large part of redaction is making sure we are not asking the TTS engine to render an alphabet soup.
Common soups are units mm/s^2 is a typical example in the sciences. In theology texts, citations are the
hard problem, the elocution module's first task is figuring out what flavour of alphabet soup a text holds.

The elocutor guesses this by parsing the bibliography and heuristics. By my current best guess, I'll need 29 components organized into 6 passes and categories to solve the theology texts use case. 

---

 Tech legend:
 RX = plain regex
 HEU = heuristic/scoring code (not a grammar)
 PC = parser combinator (parsy or hand-rolled)
 PC(t) = combinator built at runtime from a document-local table
 PC(p) = combinator parameterized by config (dialect/versification)
 DC = typed dataclass layer
 ALG = plain algorithm.

### Status checklist

At-a-glance companion to the detailed writeups below — check there for the reasoning
behind any line here.

**Foundation**
- [x] 27 `numeral_normalizer` — built, hardened (unbounded locator depth)
- [x] 28 `range_and_list` — built (`LOCATOR`, public)

**Pass 0 — sniffers**
- [x] 1 `style_sniffer` — built; validated against 3 corpora, 2 gate bugs fixed
- [x] 2 `apparatus_finder` — not needed (PDF's own TOC bounds sections)

**Pass 1 — apparatus**
- [ ] 3 `abbrev_list_parser` — out of scope so far (no abbreviations list in this corpus)
- [x] 4 `bibliography_entry_parser` — built
- [x] 5 `primary_secondary_classifier` — built, hardened (apparatus corroboration)
- [x] 6 `truncation_aligner` — not built as conceived; solved instead by
  `citation_pairing.py`'s footnote co-occurrence

**Category 1 — identity vocabularies**
- [x] 7 `biblical_sigla` — built
- [ ] 8 `clavis_numbers` — not started, no evidence
- [ ] 9 `patristic_sigla` — partial: Josephus/Philo built (adjacent, own files); Irenaeus
  evidenced (`Haer.` ×8), not yet promoted to its own
- [ ] 10 `classical_sigla` — partial: one seed entry ("Num"); Suetonius, Tacitus, Lucian,
  Dio Chrysostom, Pausanias all evidenced via `citation_pairing.py`, none built yet
- [ ] 11 `nag_hammadi_sigla` — not started, no evidence
- [ ] 12 `manuscript_sigla` — not started, no evidence

**Category 2 — intra-work locators**
- [x] 13 `biblical_locator` — subsumed: generic `mechanical_locator`/`LOCATOR` already
  handles this shape, no dedicated component needed
- [ ] 14 `internal_ref` — not built; evidenced (29/178 bare-siglum reuses in temple_gates'
  footnotes, plus a multi-locator bare-author case)
- [x] 15 `prose_hierarchical` — subsumed, same as 13
- [ ] 16 `verse_line` — not started (likely subsumed too, once a corpus needs it)
- [x] 17 `stephanus_locator` — built
- [ ] 18 `bekker_locator` — not started, no evidence
- [ ] 19 `diels_kranz` — not started, no evidence
- [ ] 20 `fragment_editor` — not started, no evidence
- [ ] 21 `nag_hammadi_locator` — not started, no evidence (stub)
- [ ] 22 `qumran_locator` — not started, no evidence (stub)

**Category 3 — edition-locators**
- [ ] 23 `migne_locator` — not started, no evidence
- [ ] 24 `critical_series_locator` — not started, no evidence
- [ ] 25 `translation_series_locator` — not started, no evidence
- [ ] 26 `papyri_epigraphy` — not started, no evidence (stub)

**Cross-cutting**
- [x] 29 `speakability_renderer` — informally satisfied (`System.speak_locator` per
  shape); not formalised as its own abstract layer
- [ ] 30 `candidate_scanner` — minimal only: `Elocutor`'s merge is static, not derived
  per document beyond the bare-author case
- [ ] 31 `grammar_activator` — minimal only: `_bare_author_systems` is a narrow,
  single-purpose instance
- [ ] 32 `dispatcher` — minimal only: `Elocutor` is "apply-all, no escalation" — the
  build order's own stated starting point

**Frontier** (next up, both already evidenced, neither blocked): finish 9/10 by
promoting the six evidenced classical/patristic authors into their own files; build 14
(a stateful "last-cited work" register). Everything else marked not started is waiting
on a corpus that actually needs it, not on being built.

#### Pass 0 — sniffers

`style_sniffer` — RX + HEU. Deps: none. **First real slice built**, narrowly: `redaction/elocution/bibliography.py`'s `sniff_style` confirms only the one axis that would actually break `bibliography_entry_parser` below (author-date's year-after-author vs. this corpus's confirmed notes-style year-at-tail) plus the same-author continuation marker's own character and repeat count — a confirm-or-abstain gate, not a dialect-choosing classifier, since a corpus of one book can only validate the one style it contains. Not built as its own file or a `DocStyle` shared beyond this one module yet — see the note below. Validated against two further real books (Couliano's *Tree of Gnosis* and *Eros and Magic*), which caught two real gaps: the confirm gate needed a *coverage* requirement, not just an absolute count, after 5 of 288 *Tree of Gnosis* entries cleared the old threshold on noise while the other 283 went unmeasured (fixed); and the continuation marker's own character was hardcoded to an em dash, when *Tree of Gnosis* uses a double hyphen and *Eros and Magic* a single one — now sniffed alongside the count (fixed). *Tree of Gnosis* still correctly abstains overall (its author-order and year-punctuation don't match this parser's one confirmed style) — the corpus-of-one caveat above is exactly why: confirming a *second* named style, rather than only tightening the gate around the first, is future work if more books need it.
`apparatus_finder` — RX + HEU (structure-dependent on your extraction format). Deps: none. Not needed yet for the corpus so far: the PDF's own TOC already bounds a bibliography section correctly (see `extraction/pdf.py`), so what looked like a detection problem turned out to be a segmentation one instead (below). Revisit once a book without a usable TOC shows up.

#### Pass 1 — apparatus

`abbrev_list_parser` — PC (leaf tokens RX); small dialect table for layout variants. Deps: 2
`bibliography_entry_parser` — PC(p), style param from 1. Deps: 1, 2. **First real slice built**, in `redaction/elocution/bibliography.py`: `authors`, `role`, `title`, `container`, `editors`, `year`, `pages` off a Chicago/SBL notes-bibliography parse, gated by `sniff_style` above. Hand-rolled backtracking (try each plausible split, longest first, keep whichever the rest of the entry validates), not a parser-combinator library — the ambiguity here (an initial's own period vs. a name/title/next-author boundary) needed one-off resolution, not composable grammar. Kept in one module with the sniffer and the classifier below, deliberately not split into the one-file-per-component layout this list otherwise suggests: there's no database or service boundary between these three to justify carving up what is, in practice, one parsing job over one list of strings — a call the project's whole build could revisit once/if a second document style shows up needing real dialect branching.
`primary_secondary_classifier` — HEU (feature scoring; could later be a tiny model). Deps: 4. **First real slice built**, also in `bibliography.py`: `classify_sources` classifies each parsed entry from structural signals — a non-empty `translator` (its own field now, not a `role` value, precisely so a consumer can't misread the translator as the work's author) is strong enough alone. 12/524 entries scored primary on temple_gates, matching a by-hand check with no false positives; recall checked against known ancient authors and every secondary entry mentioning "Translated by" — none slipped through. Validated against a second real corpus (Couliano's *Eros and Magic*), the bare/natural-order-first-author signal turned out **not** to be strong enough alone as originally shipped: "Faust. Cahiers de l'Hermétisme..." and "Soleil. Le Soleil à la Renaissance..." are anonymous themed-collection entries filed under a subject keyword, not people, and both scored primary under the old rule. Fixed by requiring the bare-name signal to be corroborated by a modern edition apparatus — a known ancient-text series (`LCL`, `Loeb Classical Library`, `Ancient Christian Writers`) or a "Translated by"/"Edited by" credit anywhere in the entry's raw text — which every genuine bare-name entry in both corpora carries and neither spurious one does. The apparatus signal alone still isn't sufficient, precisely because of the original counterexample (a modern "Introduction" essay published *inside* a Loeb-adjacent volume, correctly left secondary). Re-verified: temple_gates' 12 primary entries and 33 `citation_pairing` pairings are unchanged; Eros and Magic drops from 3 falsely-primary entries to the 1 genuine one (Bartholomaeus Anglicus). Never resolves *which* author or work an entry names — that stays `classical.py`'s boundary.
`truncation_aligner` — ALG (token-prefix alignment w/ elision & inflection tolerance; not a parser). Deps: 3, 4, 5. **Not buildable as conceived for this corpus**: aligning a bibliography title against a footnote siglum needs per-work titles, and this corpus's primary sources are collected Loeb-style entries ("Cassius Dio. Roman History.") with none. Built instead, in `redaction/elocution/citation_pairing.py`: `pair_sigla` reads a document's author-siglum vocabulary off the footnotes' own text, since a citation already names its author in full alongside the siglum ("Josephus, AJ 18.81–84") — no title-alignment needed, and no identity guessing either, since the author is only ever accepted from `bibliography.py`'s confirmed `is_primary_source` list. Verified against `temple_gates`: 33 (author, siglum) pairs across its 11 primary-source authors, all correct on inspection bar one — `collisions` correctly flagged "Ann." as claimed by both Tacitus and Suetonius, which turned out to be a genuine citation slip in the source book (footnote p83-n105 cites "Suetonius, Ann. 6.12" for what is actually a Tacitus passage) rather than a scanner bug. Measured, not built: of 178 total siglum citations, 149 pair with an author name and 29 don't (a siglum reused bare later in the same footnote, e.g. "Peregr. 28" after "Lucian, Alex. 11" two sentences earlier) — real signal a paired-only scan can't resolve alone, left for 14's stateful register rather than guessed at here.

#### Category 1 — identity vocabularies

`biblical_sigla` — PC over a static table (ships with tool; SBL forms, both period variants). Deps: 28*
`clavis_numbers` — PC, near-trivial (prefix + int + opt letter). Deps: none
`patristic_sigla` — PC(t), table compiled per-document by 6. Deps: 6
`classical_sigla` — PC(t), same mechanism + author-siglum sub-grammar. Deps: 6
`nag_hammadi_sigla` — PC, static (codex Roman + comma + Arabic; BG). Deps: 27
`manuscript_sigla` — PC, static tables (GA, Rahlfs) + generic shelfmark PC. Deps: 27

#### Category 2 — intra-work locators

`biblical_locator` — PC(p), versification param from 1. Deps: 7, 27, 28
`internal_ref` — PC(p) + stateful resolver (previous-citation register lives in dispatch, not the parser). Deps: 1, 30†
`prose_hierarchical` — PC. Deps: 27, 28
`verse_line` — PC. Deps: 27, 28
`stephanus_locator` — PC. Deps: 27, 28
`bekker_locator` — PC. Deps: 27, 28
`diels_kranz` — PC. Deps: 27, 28
`fragment_editor` — PC (parse only; resolution deferred to tiers 3–4). Deps: 27, 28
`nag_hammadi_locator` — PC. Deps: 11, 27, 28
`qumran_locator` — PC (stub). Deps: 27, 28

#### Category 3 — edition-locators

`migne_locator` — PC. Deps: 27, 28
`critical_series_locator` — PC(p), per-series dialect table (SC/CCSL/CSEL/GCS/PO/PTS…). Deps: 27, 28
`translation_series_locator` — PC. Deps: 27, 28
`papyri_epigraphy` — PC (stub). Deps: 27, 28

#### Cross-cutting

`numeral_normalizer` — RX + ALG (token-level leaf used inside PCs). Deps: none
`range_and_list` — PC (the shared sub-grammar everything imports). Deps: 27
`speakability_renderer` — DC methods (render_speech() per typed node; per-locale/per-grammar rules). Deps: every node type, i.e. 7–26

And three pieces we've discussed that weren't on the numbered list but belong in the tree because things depend on them:

`candidate_scanner` — RX + HEU: trigger-vocabulary span proposer; its trigger set is generated from the active grammar set. Deps: 31
`grammar_activator` — ALG: bibliography → active set compiler (union with always-on). Deps: 5, 6
`dispatcher` — ALG: apply-all-active, collect successes, disambiguate on resolved work, escalate ambiguity/failures. Deps: 30, 31, all PCs; owns the state for 14

### Dependency tree (arrows point at dependents; build bottom-up):

￼
                      ┌──────────── foundation layer ────────────┐
                     27 `numeral_normalizer`      1 `style_sniffer`   2 `apparatus_finder`
                           │                        │    │              │
                    28 `range_and_list`             │    └──────┬───────┤
                           │                        │           │       │
          ┌────────────────┼──────────────┐         │      3 `abbrev`   4 `biblio` ◄─(style)─┘
          │                │              │         │           │       │
          │                │              │         │           └───┬───┤
   [simple locators]  [edition loc.]  7 `biblical_sigla`            │ 5 `classifier`
 15 `prose_hier`      23 `migne`          │                         │   │
 16 `verse_line`      24 `crit_series`◄─(dialects)                  └─┬─┘
 17 `stephanus`       25 `translation`   13 `biblical_locator` ◄─(versification)─ 1
 18 `bekker`          26 `papyri`(stub)   │                       6 `truncation_aligner`
   19 `diels_kranz`          │            │                         │
   20 `fragment_ed`          │            │                    ┌────┴────┐
   22 `qumran`(stub)         │            │                9 `patristic`  10 `classical`
   11+21 `nag_hammadi`       │            │                 _sigla(t)    _sigla(t)
          │                  │            │                    │            │
          └──────────┬───────┴────────────┴──────┬─────────────┴────────────┘
                     │                           │
                     │                     31 `grammar_activator` ◄── 5, 6
                     │                           │
                     │                     30 `candidate_scanner` ◄─(trigger set)
                     │                           │
                     └────────────► 32 `dispatcher` ◄──── 14 `internal_ref` (stateful,
                                         │                    register lives here)
                                         │
                                   29 `speakability_renderer`
                                   (methods on node types from 7–26)

###### Notes on the tree's load-bearing edges:

27 → 28 → everything: the normalizer and range sub-grammar are the true root. Build and test these first in isolation — every locator bug you'd otherwise chase lands here.
6 is the keystone: nothing document-local (9, 10, 31, hence 30, 32) exists without the aligner, and the aligner needs 3+4+5. This is the critical path, matching the build order from last time.
1 feeds three consumers by parameter, not by call: 4 (bibliography style), 13 (versification default), 14 (internal-ref conventions). Model this as a DocStyle config object produced once in pass 0 and threaded through — don't let the sniffer become a service things call mid-parse.
30's trigger set is derived, not hardcoded: each PC in the active set exports its trigger vocabulary (sigla strings, series abbreviations, numeric patterns); the scanner regex is compiled per-document from that union. This keeps scanner and grammars from drifting apart — single source of truth.
29 has no inbound arrows in the pipeline sense — it's not a pass, it's methods on the dataclasses each PC emits. Its "dependency on 7–26" is just that each new node type needs its render_speech() written when the grammar lands. Enforce with an abstract method so a new grammar can't ship silently unspeakable.
14 is deliberately split: the parser is trivial PC; the resolver is dispatcher state. Keeping the register in 32 preserves the parse-permissively/validate-in-dispatch rule.
Build order restated against the tree: 27, 28 → 1, 2 → 3, 4, 5 → 6 → 7, 13 → 15 → 9, 10 → 31, 30, 32 (minimal versions — 32 can start as "apply all, no escalation") → 23, 24 → 17, 18 → 14 → 29 progressively → the rest by corpus demand. The stubs (22, 26) cost one file each of trigger vocabulary so the scanner at least flags them for tier 3 rather than silently skipping.
