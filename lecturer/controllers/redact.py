import sys

from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT, _PROVIDER_ARGUMENTS
from lecturer.phases import _extract_phase, _provider, _redact_phase
from lecturer.workdir import _existing_workdir
from redaction import (
    DEFAULT_MODELS,
    TAGGING_MODELS,
    FootnoteWeaver,
    Glossator,
    ProviderError,
    Script,
    TongueInterpreter,
    check_budget,
    ensure_synopsis,
    estimate_gloss_cost,
    render_estimate,
)
from redaction.mend import SeamMender


class Redact(Controller):
    class Meta:
        label = "redact"
        stacked_on = "base"
        stacked_type = "nested"
        help = "rework the extraction into redactions/<variant>/"
        description = (
            "Rework the extracted text, layer by layer, into a spoken script. "
            "The weaver decides the variant: notes dropped (book, the default), "
            "woven by the LLM glossator (--llm -> glossed), or verbatim "
            "(--verbatim-notes -> verbatim)."
        )
        arguments = [
            _OUTPUT_ARGUMENT,
            (
                ["--llm"],
                {
                    "help": "weave footnotes in as spoken digressions with the LLM "
                    "glossator (billed API calls; cached in the work dir)",
                    "action": "store_true",
                    "dest": "llm",
                },
            ),
            (
                ["--verbatim-notes"],
                {
                    "help": "weave every footnote in verbatim at its anchor "
                    "(inspection mode; unpleasant listening)",
                    "action": "store_true",
                    "dest": "verbatim_notes",
                },
            ),
            (
                ["--interpret"],
                {
                    "help": "tag Latin-alphabet language switches (loanwords, Latin "
                    "phrases, names) with the LLM (cheap model by default; cached)",
                    "action": "store_true",
                    "dest": "interpret",
                },
            ),
            (
                ["--budget"],
                {
                    "help": "refuse to run --llm if the estimated cost exceeds this many "
                    "dollars (checked against whatever part of the estimate is actually "
                    "priced; a hard ceiling, not overridden by --yes)",
                    "dest": "budget",
                    "metavar": "DOLLARS",
                    "type": float,
                },
            ),
            (
                ["--yes"],
                {
                    "help": "skip the interactive confirmation before --llm spends "
                    "anything (for scripted/non-interactive runs); --budget still applies",
                    "action": "store_true",
                    "dest": "yes",
                },
            ),
            *_PROVIDER_ARGUMENTS,
        ]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        weaver = None
        interpreter = None
        if self.app.pargs.verbatim_notes:
            weaver = FootnoteWeaver()
        try:
            if self.app.pargs.llm:
                provider = _provider(self.app, DEFAULT_MODELS)
                synopsis_path = directory / "synopsis.txt"
                synopsis = synopsis_path.read_text().strip() if synopsis_path.exists() else None
                glossator = Glossator(
                    provider=provider,
                    cache_path=directory / "gloss_cache.json",
                    synopsis=synopsis,
                    log=self.app.log.info,
                )
                script = SeamMender().redact(Script.from_extraction(extraction))
                stale = glossator.stale_cache_entries(script)
                if stale:
                    self.app.log.warning(
                        f"{stale} of {glossator.cache_size} cached gloss(es) in "
                        f"gloss_cache.json don't match any paragraph under {provider.label} "
                        "— most likely glossed under a different model or prompt; those "
                        "paragraphs will be re-sent and re-billed this run"
                    )
                if self.app.pargs.provider == "anthropic":
                    estimate = estimate_gloss_cost(extraction, provider, directory, synopsis)
                    print(render_estimate(estimate))
                    proceed = self._confirm_spend(estimate)
                else:
                    # count_tokens (and so estimate_gloss_cost) is Anthropic-only — no
                    # identically-named free endpoint exists for OpenAI/local models
                    # (see docs/planned/cost-estimate.md's own scoping). The gate still
                    # runs, just without a priced estimate to gate on; --budget can't be
                    # honoured here, so it errors out rather than silently not applying.
                    if self.app.pargs.budget is not None:
                        self.app.log.error(
                            "--budget needs --provider anthropic — there's no free "
                            f"token-counting endpoint for {provider.label} to check a "
                            "ceiling against."
                        )
                        self.app.exit_code = 1
                        return
                    remaining = len(glossator.pending_paragraphs(script))
                    proceed = self._confirm_unpriced_spend(remaining, synopsis is None, provider)
                if not proceed:
                    self.app.exit_code = 1
                    return
                if synopsis is None:
                    synopsis = ensure_synopsis(
                        extraction, provider, synopsis_path, log=self.app.log.info
                    )
                    glossator.use_synopsis(synopsis)
                weaver = glossator
            if self.app.pargs.interpret:
                interpreter = TongueInterpreter(
                    provider=_provider(self.app, TAGGING_MODELS),
                    cache_path=directory / "tongue_cache.json",
                    log=self.app.log.info,
                )
        except ProviderError as error:
            self.app.log.error(str(error))
            self.app.exit_code = 1
            return
        _redact_phase(self.app, directory, extraction, weaver=weaver, interpreter=interpreter)

    def _confirm_spend(self, estimate) -> bool:
        """Gate before any billed --llm call — see docs/planned/budget-confirmation.md.

        ``--budget`` is a hard ceiling checked first and never bypassed by
        ``--yes``: the two stay orthogonal, ``--yes`` only ever answers the
        question a human would otherwise be asked, never the budget itself.
        Skipped entirely when there's nothing left to spend on (every
        annotated paragraph already cached and a synopsis already on disk),
        so a fully-cached re-run of --llm never demands an answer for a
        no-op.
        """
        if estimate.remaining_paragraphs == 0 and estimate.synopsis_tokens == 0:
            return True
        if self.app.pargs.budget is not None:
            refusal = check_budget(estimate, self.app.pargs.budget)
            if refusal is not None:
                self.app.log.error(f"refusing to spend: {refusal}")
                return False
        return self._ask_to_proceed()

    def _confirm_unpriced_spend(
        self, remaining_paragraphs: int, needs_synopsis: bool, provider
    ) -> bool:
        """Same gate as ``_confirm_spend``, for a provider with no priced estimate.

        Only reached for a non-Anthropic provider, where ``estimate_gloss_cost``
        can't run at all (no free ``count_tokens``-equivalent) — see the
        ``--provider`` branch in ``_default``. ``--budget`` is refused before this
        is ever called, so there's nothing left to check here beyond the human.
        """
        if not remaining_paragraphs and not needs_synopsis:
            return True
        parts = []
        if needs_synopsis:
            parts.append("draft this book's synopsis.txt with one real billed call")
        if remaining_paragraphs:
            word = "paragraph" if remaining_paragraphs == 1 else "paragraphs"
            parts.append(f"gloss {remaining_paragraphs} remaining {word}")
        print(
            f"This run will {' and '.join(parts)} on {provider.label}. No free "
            "token-counting endpoint exists for this provider, so the cost can't be "
            "estimated in advance — check gloss_usage.jsonl after the run for what it "
            "actually cost."
        )
        return self._ask_to_proceed()

    def _ask_to_proceed(self) -> bool:
        if self.app.pargs.yes:
            return True
        if not sys.stdin.isatty():
            self.app.log.error(
                "redact --llm needs confirmation before spending anything, and this "
                "session isn't interactive — pass --yes to confirm without a prompt."
            )
            return False
        try:
            answer = input("Proceed with this spend? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            self.app.log.error("aborted before spending anything.")
            return False
        return True
