SHELL := /bin/bash

IMAGE ?= ghcr.io/vshulcz/toy-load:latest

.PHONY: fmt vet test build docker-build docker-push helm-template kind-deploy

fmt:
	go fmt ./...

vet:
	go vet ./...

test:
	go test ./...

build:
	mkdir -p bin
	CGO_ENABLED=0 go build -o bin/toy-load ./cmd/toy-load

docker-build:
	docker build -t $(IMAGE) .

docker-push:
	docker push $(IMAGE)

helm-template:
	helm template toy-load deploy/helm/toy-load

kind-deploy:
	kubectl apply -f deploy/manifests
