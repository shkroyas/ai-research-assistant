.PHONY: install lint format test run

install:  ## Install app and dev dependencies
	uv sync

lint:  ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-fix lint issues and format code
	uv run ruff check --fix .
	uv run ruff format .

test:  ## Run the offline test suite with coverage
	uv run pytest --cov --cov-report=term-missing

run:  ## Start the Streamlit app
	uv run streamlit run app/streamlit_app.py
