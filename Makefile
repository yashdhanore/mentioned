.PHONY: dev dev-down dev-logs

dev:
	./scripts/dev-up.sh

dev-down:
	./scripts/dev-down.sh

dev-logs:
	tail -f .dev-logs/*.log
