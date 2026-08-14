# Spec: confirmation gate + budget option for `redact --llm`

Status: not started. Depends on `docs/planned/cost-estimate.md` (needs its estimate to show
something before asking). Written for handoff to a fresh session — self-contained.

## Purpose

Never let `redact --llm` start spending money silently. Show the estimate from
`cost-estimate.md`, then require an explicit affirmative before any billed call happens.
This is the project's existing abstain-over-guess posture (CLAUDE.md's standing constraint
on the LLM's role) applied to spend, not just to content — and it's the actual accessible
"magic" for this audience: not automating the decision away, but making the stopping point
real. A blind user can't eyeball a dashboard to sanity-check a run's cost after the fact;
a plain-prose number plus an explicit yes/no before it happens is the thing that works.

## Functional requirements

1. Before `redact --llm` proceeds to any billed call:
   - Compute the estimate (`cost-estimate.md`).
   - Print it as plain prose (not a table).
   - Prompt for an explicit affirmative (`y` / `yes`). Anything else — including EOF or a
     non-interactive session with no override flag — aborts before spending anything.
2. Optional `--budget N` (a dollar ceiling): when set and the estimate exceeds it, refuse
   outright rather than just asking, and say by how much in prose — "the estimate is $X
   over your $N budget" — not "add $X to your account," since there's no account-balance or
   top-up mechanism to offer (see `cost-estimate.md`'s non-goals; the original ask for
   auto-top-up isn't buildable against the real API and was descoped in conversation before
   this spec was written).
3. A bypass flag skips the confirmation prompt entirely, for scripted/non-interactive runs
   where no human is present to answer. **Naming — do not default to something clever.**
   The user considered `--like_thanes` and rejected it themselves on accessibility grounds
   (principle of least surprise: a flag name should say what it does without requiring a
   literary reference to decode). Candidates to weigh at implementation time: `--yes`,
   `--no-confirm`, `--skip-budget-check`, `--force`. Whatever is chosen, document it
   plainly in `--help` text, matching this project's existing tone (see `docs/contributing.md`).

## Non-goals

- Doesn't re-derive or re-litigate the estimate's accuracy — that's `cost-estimate.md`'s job.
- No cumulative/running budget across multiple invocations — a per-run ceiling only, unless
  a future need for cross-run tracking shows up for real (don't build it speculatively).

## Open questions for whoever implements this

- `--budget` and the confirmation gate apply only to `--llm` (the only path in `redact` that
  makes billed calls) — `--verbatim-notes` and the default book/NoteDropper weave spend
  nothing and shouldn't be gated.
- `draft-lexicon`, `draft-classical`, and `TongueInterpreter` also make billed calls (cheap
  tier) but through a different code path entirely. Whether the same estimate+confirm gate
  should eventually cover them too is a natural follow-up — flag it, don't build it now.

## Settled already, no spec needed — do this whenever, it's one line

`AnthropicProvider.ask` (`redaction/providers.py:92`) hardcodes `max_tokens=8000`, shared
between adaptive thinking and the visible response. When both together exceed it, the
response truncates mid-JSON (this already crashed a real run this session — see the
`ValidationError` catch added at `redaction/providers.py:112-113`, which contains the crash
but still silently falls back every truncated paragraph to the deterministic weave with no
log line). Raising the constant (e.g. to 24000) costs nothing on paragraphs that don't need
it — you're billed for tokens actually generated, not the ceiling — and removes the
truncation class outright. No per-call detection needed; that idea was considered and
dropped as solving a problem that doesn't exist (the ceiling isn't a cost lever). Worth
pairing with a log line on fallback while touching this code, so a truncation-triggered
fallback isn't invisible.
