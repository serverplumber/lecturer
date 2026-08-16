from cement import Controller

from lecturer.arguments import _OUTPUT_ARGUMENT, _SECTIONS_ARGUMENT, _VARIANT_ARGUMENT
from lecturer.phases import _apparatus_skip, _ensure_redactions, _recite_phase
from lecturer.workdir import _existing_workdir


class Recite(Controller):
    class Meta:
        label = "recite"
        stacked_on = "base"
        stacked_type = "nested"
        help = "speak redactions/<variant>/ into audio/<variant>/"
        description = (
            "Synthesise the redacted script into one WAV per section with Kokoro. "
            "Unchanged sections (by content signature) are kept; apparatus "
            "sections are skipped unless --sections says otherwise."
        )
        arguments = [
            _OUTPUT_ARGUMENT,
            _VARIANT_ARGUMENT,
            _SECTIONS_ARGUMENT,
            (
                ["--voice"],
                {
                    "help": "Kokoro voice, or a blend like af_kore+af_aoede "
                    "(weighted: af_kore:2+af_aoede:1)",
                    "dest": "voice",
                    "metavar": "VOICE",
                    "default": "af_kore+af_aoede",
                },
            ),
            (
                ["--speed"],
                {
                    "help": "speech rate multiplier (0.5-2.0)",
                    "dest": "speed",
                    "metavar": "FACTOR",
                    "type": float,
                    "default": 1.0,
                },
            ),
        ]

    def _default(self):
        directory = _existing_workdir(self.app)
        if directory is None:
            return
        script = _ensure_redactions(self.app, directory)
        if script is None:
            return
        _recite_phase(
            self.app,
            directory,
            script,
            self.app.pargs.variant,
            skip=_apparatus_skip(self.app.pargs.sections),
            voice=self.app.pargs.voice,
            speed=self.app.pargs.speed,
        )
