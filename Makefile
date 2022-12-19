
.phony: lint
lint:
	isort event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ tests/
	black event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ tests/
	mypy event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ tests/
	flake8 event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ tests/
	 
