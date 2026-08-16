"""CLI argument tuples shared across more than one verb's ``Meta.arguments``."""

from redaction import PROVIDERS

_OUTPUT_ARGUMENT = (
    ["-o", "--output"],
    {
        "help": "the working directory (default: derived from the document name)",
        "dest": "output",
        "metavar": "DIR",
    },
)

_VARIANT_ARGUMENT = (
    ["--variant"],
    {
        "help": "which weaving to work from: book, glossed, or verbatim",
        "dest": "variant",
        "metavar": "NAME",
        "default": "book",
    },
)

_SECTIONS_ARGUMENT = (
    ["--sections"],
    {
        "help": "only sections whose title matches this regex (default: everything "
        "except apparatus — front matter, bibliography, index, ...)",
        "dest": "sections",
        "metavar": "REGEX",
    },
)

_PROVIDER_ARGUMENTS = [
    (
        ["--provider"],
        {
            "help": "LLM provider",
            "dest": "provider",
            "choices": sorted(PROVIDERS),
            "default": "anthropic",
        },
    ),
    (
        ["--model"],
        {
            "help": "model override (defaults per provider and task)",
            "dest": "model",
            "metavar": "MODEL",
        },
    ),
    (
        ["--base-url"],
        {
            "help": "OpenAI-compatible endpoint, for local models "
            "(e.g. http://localhost:11434/v1 for Ollama)",
            "dest": "base_url",
            "metavar": "URL",
        },
    ),
    (
        ["--effort"],
        {
            "help": "reasoning effort (low/medium/high; local reasoning models "
            "like gpt-oss need high)",
            "dest": "effort",
            "metavar": "LEVEL",
        },
    ),
]
