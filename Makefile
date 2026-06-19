.PHONY: dev test deploy

dev:
	process-compose up

test:
	uv run pytest --cov=lilwman --cov-report=term-missing

deploy:
	rsync -av \
		--exclude='.venv' \
		--exclude='.env' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		--exclude='.git' \
		. gigi:/opt/lilwman/
	ssh gigi "cd /opt/lilwman && uv sync && sudo systemctl restart lilwman"
