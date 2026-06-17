.PHONY: test lint build clean dataset train

test:
	python3 -m pytest tests/ -v --tb=short

lint:
	@echo "Compile-checking all Python files..."
	@find . -name '*.py' -not -path './frontend/*' -not -path './.git/*' -exec python3 -m py_compile {} +
	@echo "All files OK."

build:
	python3 -m build

clean:
	rm -rf dist/ build/ *.egg-info **/*.egg-info

dataset:
	python3 -m dataset.generate_dataset

train:
	python3 -m model.train
