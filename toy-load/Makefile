SHELL := /bin/bash

IMAGE ?= ghcr.io/vshulcz/toy-load:latest
BINARY ?= bin/toy-load
CHART ?= deploy/helm/toy-load
VERSION ?= dev
REVISION ?= $(shell git rev-parse --short HEAD 2>/dev/null || printf unknown)
CREATED ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ)

.PHONY: help run fmt fmt-check vet test test-race check coverage build docker-build docker-push helm-lint helm-template deploy-manifests

help:
	@printf "%-18s %s\n" "fmt" "Format Go sources"
	@printf "%-18s %s\n" "run" "Run toy-load locally"
	@printf "%-18s %s\n" "fmt-check" "Fail if gofmt would change files"
	@printf "%-18s %s\n" "vet" "Run go vet"
	@printf "%-18s %s\n" "test" "Run Go test suite"
	@printf "%-18s %s\n" "test-race" "Run Go race test suite"
	@printf "%-18s %s\n" "check" "Run local checks used by CI"
	@printf "%-18s %s\n" "coverage" "Generate Go coverage report"
	@printf "%-18s %s\n" "build" "Build bin/toy-load"
	@printf "%-18s %s\n" "docker-build" "Build container image"
	@printf "%-18s %s\n" "docker-push" "Push container image"
	@printf "%-18s %s\n" "helm-lint" "Lint Helm chart"
	@printf "%-18s %s\n" "helm-template" "Render Helm manifests"
	@printf "%-18s %s\n" "deploy-manifests" "Apply raw Kubernetes manifests"

run:
	go run ./cmd/toy-load

fmt:
	go fmt ./...

fmt-check:
	@fmt_output="$$(gofmt -l .)"; \
	if [[ -n "$$fmt_output" ]]; then \
		printf 'Run gofmt on:\n%s\n' "$$fmt_output"; \
		exit 1; \
	fi

vet:
	go vet ./...

test:
	go test ./...

test-race:
	go test -race ./...

check: fmt-check vet test helm-lint helm-template

coverage:
	mkdir -p ../coverage
	go test ./... -covermode=atomic -coverprofile=../coverage/toy-load.out
	go tool cover -func=../coverage/toy-load.out | tee ../coverage/toy-load.txt

build:
	mkdir -p $(dir $(BINARY))
	CGO_ENABLED=0 go build -trimpath -o $(BINARY) ./cmd/toy-load

docker-build:
	docker build \
		--build-arg VERSION=$(VERSION) \
		--build-arg REVISION=$(REVISION) \
		--build-arg CREATED=$(CREATED) \
		-t $(IMAGE) .

docker-push:
	docker push $(IMAGE)

helm-lint:
	helm lint $(CHART)

helm-template:
	helm template toy-load $(CHART)

deploy-manifests:
	kubectl apply -f deploy/manifests
