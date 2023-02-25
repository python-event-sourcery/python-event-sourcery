
.phony: lint
lint:
	isort event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ event_sourcery_kombu/ tests/
	black event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ event_sourcery_kombu/ tests/
	mypy event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ event_sourcery_kombu/ tests/
	flake8 event_sourcery/ event_sourcery_pydantic/ event_sourcery_sqlalchemy/ event_sourcery_kombu/ tests/
	 
