from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT, _PROVIDER_ARGUMENTS, _VARIANT_ARGUMENT
from lecturer.phases import _ensure_redactions, _provider
from lecturer.workdir import _existing_workdir
from redaction import TAGGING_MODELS, ProviderError


class DraftLexicon(Controller):
    class Meta:
        label = "draft-lexicon"
        stacked_on = "base"
        stacked_type = "nested"
        help = "draft lexicon.json pronunciation entries, then stop for review"
        description = (
            "Sweep the redacted script for pronunciation risks with a cheap "
            "model and merge draft entries into the work dir's lexicon.json — "
            "then stop: validate the drafts by ear before recite/publish. "
            "Existing entries are never overwritten. Redacts first if needed."
        )
        arguments = [_OUTPUT_ARGUMENT, _VARIANT_ARGUMENT, *_PROVIDER_ARGUMENTS]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        script = _ensure_redactions(self.app, directory)
        if script is None:
            return
        from recitation import draft

        try:
            draft(
                script,
                _provider(self.app, TAGGING_MODELS),
                directory / "lexicon.json",
                log=self.app.log.info,
            )
        except ProviderError as error:
            self.app.log.error(f"lexicon draft failed: {error}")
            self.app.exit_code = 1
