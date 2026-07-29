# Growing the classical sigla table

`classical.py`'s author-work abbreviations ("Or." → "Oration", "AJ" → "Jewish Antiquities")
are open-vocabulary — no book finishes this table. `redaction/elocution/canon.py` splits it
into two files instead of one hardcoded dict; this is how to actually work with them. The *why*
(TOML for both, precedence, the stub mechanism) is in `CLAUDE.md`'s `classical.py` /
`draft-classical` entries — this doc is the *how*.

## The two files

- **Tier 1** — `elocution_dir/classical.toml`. This machine's canon, shared across every book.
  `elocution_dir` defaults to `~/.config/lecturer/elocution`; a dev checkout usually points it
  in-repo instead (`docs/contributing.md`). Hand-edit this directly for anything you're
  confident is a universal fact, or let `promote-classical` write to it.
- **Tier 2** — `<work dir>/classical.toml`. One document's own entries — hand-edited, or
  drafted by `draft-classical`. Never touches tier 1.

A citation resolves through seed (the one hardcoded entry in `classical.py`) → tier 1 → tier 2,
each layer able to override the last.

## Drafting

```sh
lecturer draft-classical -o temple_gates
```

This reads the document's own bibliography and footnotes (`citation_pairing.py`'s
`pair_sigla` — already-confirmed author, unknown siglum) and asks a cheap model to expand each
one. A real run against `temple_gates` resolved candidates like:

```toml
"AJ" = {spoken = "Jewish Antiquities", count = 20}
"Ner." = {spoken = "Nero", count = 7}
```

`count` is bookkeeping (how often the siglum was cited), not read by anything downstream — safe
to ignore or delete.

Existing resolved entries are never touched, so `draft-classical` is safe to re-run any time —
after adding a chapter, after a better model comes out, whatever. It'll only ever add what's
missing.

## Reading a stub

Not every siglum resolves. Two things stop a draft: the siglum is ambiguous in this document
(paired with more than one author), or the model wasn't confident. Either way, it lands as a
**stub** — no `spoken` key, so it's inert (`Elocutor` never sees it) — with a comment and
enough context to resolve by hand. A real one, from `temple_gates`:

```toml
# ambiguous in this document — add "spoken" once you know which
"Ann." = {candidates = {Suetonius = 1, Tacitus = 13}, bibliography = {Suetonius = ["Suetonius. Translated by J. C. Rolfe. 3 vols. LCL. 2nd edition. Cambridge: Harvard University Press, 1998."], Tacitus = ["Tacitus. The Histories and the Annals. Translated by Clifford H. Moore and John Jackson. 4 vols. LCL. Cambridge: Harvard University Press, 1937."]}}
```

`candidates` gives each author's citation count in this document; `bibliography` is that
author's own bibliography entry, verbatim, so you don't have to go find it. Here the count
(13 vs. 1) and the title itself both point at Tacitus's *Annals* — but don't take that as a
rule, some books really do cite two authors under the same siglum on purpose. Resolve it by
adding `spoken` to the same inline table:

```toml
"Ann." = {spoken = "Annals", candidates = {Suetonius = 1, Tacitus = 13}, bibliography = {...}}
```

The rest of the table (`candidates`, `bibliography`) is inert once `spoken` is set — leave it
or delete it, both are fine. Re-running `draft-classical` afterward leaves a resolved entry
alone, stub or not.

## Promoting

Once you trust an entry enough to apply to every book, not just this one:

```sh
lecturer promote-classical -o temple_gates
```

Copies every *resolved* tier-2 entry not already in tier 1 into the shared canon — additive
only, never overwrites, safe to run repeatedly (a second run reports "nothing new to
promote"). Only `spoken` travels; a stub's `candidates`/`bibliography` are this document's own
scratch context; the shared canon shouldn't carry them.

Don't promote an entry you're not sure generalizes — a document-specific correction is fine
left in tier 2 forever.
