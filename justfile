# List available recipes
default:
    @just --list

# Install dependencies and git hooks (run once after cloning)
setup:
    uv sync
    uv run pre-commit install

# Lint (and auto-fix what ruff can)
lint:
    uv run ruff check --fix

# Format the code
fmt:
    uv run ruff format

# Lint + format, same as the commit hooks
check: lint fmt

# Run lecturer, e.g. `just run extract -o eros_magic texts/some_book.epub`,
# then `just run -o eros_magic` for the whole chain (see `just run --help` for verbs)
run *args:
    uv run lecturer {{args}}
