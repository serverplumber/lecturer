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
            "Turn monographs into audiobooks. Bare `lecturer -o DIR` runs the "
            "whole chain to publish with default settings; the verbs run one "
            "phase each, reading the previous phase's files from the work dir."
        )
        arguments = [_OUTPUT_ARGUMENT]

    def _default(self):
        directory = Path(self.app.pargs.output) if self.app.pargs.output else None
        if directory is None or not (directory / WORKING_TEXT).exists():
            self.app.args.print_help()
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
