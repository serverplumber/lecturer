from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT, _SECTIONS_ARGUMENT, _VARIANT_ARGUMENT
from lecturer.phases import _apparatus_skip, _ensure_redactions, _publish_phase, _recite_phase
from lecturer.workdir import _existing_workdir


class Publish(Controller):
    class Meta:
        label = "publish"
        stacked_on = "base"
        stacked_type = "nested"
        help = "bind audio/<variant>/ into Opus plus an M3U playlist"
        description = (
            "Convert recited WAVs to Opus (~10x smaller) and write a playlist "
            "with section titles and durations, in reading order."
        )
        arguments = [_OUTPUT_ARGUMENT, _VARIANT_ARGUMENT, _SECTIONS_ARGUMENT]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        script = _ensure_redactions(self.app, directory)
        if script is None:
            return
        variant = self.app.pargs.variant
        skip = _apparatus_skip(self.app.pargs.sections)
        if not any((directory / "audio" / variant).glob("*.wav")):
            self.app.log.info(f"no {variant} audio yet; reciting first (default voice)")
            _recite_phase(self.app, directory, script, variant, skip=skip)
        _publish_phase(self.app, directory, script, variant, skip=skip)
