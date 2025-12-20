FROM golang:1.25 as builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go env -w GO111MODULE=on && go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/toy-load ./cmd/toy-load

FROM gcr.io/distroless/base-debian12
LABEL org.opencontainers.image.source="https://github.com/vshulcz/mpc-autoscaler"
WORKDIR /
COPY --from=builder /out/toy-load /toy-load
USER 65532:65532
EXPOSE 9090
ENTRYPOINT ["/toy-load"]
