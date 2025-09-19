IMAGE_NAME ?= telegram-auto-read

.PHONY: docker-build

docker-build:
	docker build -t $(IMAGE_NAME) .
