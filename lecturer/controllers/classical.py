from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT, _PROVIDER_ARGUMENTS
from lecturer.phases import _elocution_dir, _extract_phase, _provider
from lecturer.workdir import _existing_workdir
from redaction import DEFAULT_MODELS, ProviderError


class DraftClassical(Controller):
    class Meta:
        label = "draft-classical"
        stacked_on = "base"
        stacked_type = "nested"
        help = "draft classical_sigla.toml (tier 2) author-work sigla, then stop for review"
        description = (
            "Sweep this document's own bibliography and footnotes (via "
            "citation_pairing.py's pair_sigla) for author-work abbreviations no "
            "system already resolves, and ask a model for each one's spoken title "
            "— then stop: check the drafts by eye (redact picks them up "
            "automatically from here on), and run promote-classical once you trust "
            "one enough for every book. Defaults to DEFAULT_MODELS, not the cheap "
            "tagging tier: classical-title expansion needs real classical "
            "knowledge a small model doesn't reliably have. Existing entries are "
            "never overwritten."
        )
        arguments = [_OUTPUT_ARGUMENT, *_PROVIDER_ARGUMENTS]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        from redaction.elocution.draft import draft

        try:
            draft(
                extraction,
                _provider(self.app, DEFAULT_MODELS),
                _elocution_dir(self.app),
                directory,
                log=self.app.log.info,
            )
        except ProviderError as error:
            self.app.log.error(f"classical draft failed: {error}")
            self.app.exit_code = 1


class PromoteClassical(Controller):
    class Meta:
        label = "promote-classical"
        stacked_on = "base"
        stacked_type = "nested"
        help = "merge this document's classical_sigla.toml (tier 2) into the shared canon"
        description = (
            "Copy every entry in this work dir's classical_sigla.toml (this document's "
            "own author-work sigla) into the shared, hand-curated canon at "
            "elocution_dir/classical_sigla.toml — used by every book from here on. "
            "Additive only: a siglum the canon already has is left untouched. "
            "Run it once you've checked a hand-added or drafted entry by ear."
        )
        arguments = [_OUTPUT_ARGUMENT]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        from redaction.elocution.canon import promote, tier1_path

        elocution_dir = _elocution_dir(self.app)
        added = promote(elocution_dir, directory, "classical")
        if added:
            self.app.log.info(
                f"promoted {len(added)} entr{'y' if len(added) == 1 else 'ies'} into "
                f"{tier1_path(elocution_dir, 'classical')}: {', '.join(sorted(added))}"
            )
        else:
            self.app.log.info("nothing new to promote")
