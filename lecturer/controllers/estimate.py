from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT, _PROVIDER_ARGUMENTS
from lecturer.phases import _extract_phase, _provider
from lecturer.workdir import _existing_workdir
from redaction import DEFAULT_MODELS, ProviderError, estimate_gloss_cost, render_estimate


class EstimateGloss(Controller):
    class Meta:
        label = "estimate-gloss"
        stacked_on = "base"
        stacked_type = "nested"
        help = "print a real cost estimate for redact --llm, without spending anything"
        description = (
            "Compute and print what the remaining redact --llm work would cost, using "
            "count_tokens (free) for input and this book's own gloss_usage.jsonl call "
            "history for output. Spends nothing. Anthropic only for now."
        )
        arguments = [_OUTPUT_ARGUMENT, *_PROVIDER_ARGUMENTS]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        if self.app.pargs.provider != "anthropic":
            self.app.log.error(
                "estimate-gloss only supports --provider anthropic for now "
                "(no free token-counting endpoint for OpenAI)"
            )
            self.app.exit_code = 1
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        try:
            provider = _provider(self.app, DEFAULT_MODELS)
        except ProviderError as error:
            self.app.log.error(str(error))
            self.app.exit_code = 1
            return
        synopsis_path = directory / "synopsis.txt"
        synopsis = synopsis_path.read_text().strip() if synopsis_path.exists() else None
        estimate = estimate_gloss_cost(extraction, provider, directory, synopsis)
        print(render_estimate(estimate))
