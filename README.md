# Lecturer

Lecturer is a text-to-voice pipeline which takes monographs as input and produces an audio output
which sounds like a lecturer reading his own book. The first hard bit is extracting footnotes and
providing them to an LLM so it can turn the footnotes into digressions which flow with the text.
I'll start with [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) for the TTS.

## Usage

```sh
lecturer -o eros_magic "texts/Ioan P. Couliano - Eros and Magic in the Renaissance.epub"
```

This creates `./eros_magic/`, copies the document into it, links `./eros_magic/working_text`
to the copy, and extracts the text into `./eros_magic/sections/` — one text file per section
(front matter lumped together) with a matching `.footnotes.txt` file beside it. All further
intermediary files and the final audio land in the same directory.

## Development

Requires [uv](https://docs.astral.sh/uv/), [just](https://just.systems/), and optionally
[direnv](https://direnv.net/).

```sh
just setup   # install dependencies and commit hooks
just         # list the other recipes
```
