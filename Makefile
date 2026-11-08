install:
	uv sync

project:
	uv run project

build:
	uv build

publish:
	uv build
	uvx twine check dist/*

package-install:
	uv tool install dist/*.whl --force

lint:
	uv run ruff check .
