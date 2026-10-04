from pathlib import Path

from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT
from lecturer.phases import (
    _apparatus_skip,
    _extract_phase,
    _publish_phase,
    _recite_phase,
    _redact_phase,
)
from lecturer.workdir import WORKING_TEXT


class Base(Controller):
    class Meta:
        label = "base"
        description = (
            "Turn monographs into audiobooks. The pipeline is four ordered steps, "
            "numbered 1-4 below (extract -> redact -> recite -> publish), each "
            "reading the previous step's files from the work dir; bare `lecturer "
            "-o DIR` runs all four with default settings. The other verbs "
            "(marked optional below) are utilities you can run alongside the "
            "pipeline where useful, not additional required steps."
        )
        epilog = (
            "Typical order: extract, redact [--llm], recite, publish. "
            "estimate-gloss checks redact --llm's cost before you spend anything "
            "on it. draft-lexicon and draft-classical/promote-classical draft and "
            "graduate pronunciation/citation data you can review by hand; run "
            "them after redact, whenever their own --help says they fit."
        )
        arguments = [_OUTPUT_ARGUMENT]

    def _default(self):
        directory = Path(self.app.pargs.output) if self.app.pargs.output else None
        if directory is None or not (directory / WORKING_TEXT).exists():
            # cement's ArgumentHandler interface omits print_help; the argparse
            # handler actually in use is an ArgumentParser and has it.
            self.app.args.print_help()  # ty: ignore[unresolved-attribute]
            if directory is not None:
                self.app.log.error(
                    f"no {WORKING_TEXT} in {directory}: run `lecturer extract -o "
                    f"{directory} <document>` first"
                )
                self.app.exit_code = 1
            return
        extraction = _extract_phase(self.app, directory, None)
        if extraction is None:
            return
        script = _redact_phase(self.app, directory, extraction, weaver=None, interpreter=None)
        _recite_phase(self.app, directory, script, "book", skip=_apparatus_skip(None))
        _publish_phase(self.app, directory, script, "book", skip=_apparatus_skip(None))
