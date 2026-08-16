from pathlib import Path

from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT
from lecturer.phases import _extract_phase
from lecturer.workdir import WORKING_TEXT, _reconcile, slugify


class Extract(Controller):
    class Meta:
        label = "extract"
        stacked_on = "base"
        stacked_type = "nested"
        help = "set up the work dir and extract sections/ from the document"
        description = "Set up the working directory and extract the document into sections/."
        arguments = [
            _OUTPUT_ARGUMENT,
            (
                ["document"],
                {
                    "help": "path to the monograph (epub, pdf, ...); optional when "
                    "the work dir already has a working_text",
                    "nargs": "?",
                },
            ),
        ]

    def _default(self):
        document = Path(self.app.pargs.document) if self.app.pargs.document else None
        if document is None:
            if self.app.pargs.output:
                link = Path(self.app.pargs.output) / WORKING_TEXT
                if link.exists():
                    document = link.resolve()
            if document is None:
                self.app.args.print_help()
                return
        elif not document.is_file():
            self.app.log.error(f"no such document: {document}")
            self.app.exit_code = 1
            return
        directory = Path(self.app.pargs.output or slugify(document.stem))
        if not _reconcile(self.app, document, directory):
            return
        _extract_phase(self.app, directory, document)
