FROM golang:1.26 AS builder
ARG TARGETOS=linux
ARG TARGETARCH
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd/ cmd/
COPY internal/ internal/
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} go build -trimpath -o /out/toy-load ./cmd/toy-load

FROM gcr.io/distroless/static-debian12:nonroot
ARG VERSION=dev
ARG REVISION=unknown
ARG CREATED=unknown
LABEL org.opencontainers.image.title="toy-load" \
      org.opencontainers.image.description="Controllable HTTP load service for Kubernetes autoscaling experiments" \
      org.opencontainers.image.source="https://github.com/vshulcz/mpc-autoscaler" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.created="${CREATED}"
WORKDIR /
COPY --from=builder --chown=65532:65532 /out/toy-load /toy-load
USER 65532:65532
EXPOSE 9090
ENTRYPOINT ["/toy-load"]
