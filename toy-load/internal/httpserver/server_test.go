package httpserver

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/testutil"

	"github.com/vshulcz/mpc-autoscaler/toy-load/internal/config"
	"github.com/vshulcz/mpc-autoscaler/toy-load/internal/metrics"
	"github.com/vshulcz/mpc-autoscaler/toy-load/internal/workload"
)

func newTestServer(t *testing.T) (*Server, *metrics.Collectors) {
	t.Helper()

	cfg := config.Config{
		MetricsPath: "/metrics",
	}
	logger := slog.New(slog.NewTextHandler(io.Discard, &slog.HandlerOptions{Level: slog.LevelDebug}))
	reg := prometheus.NewRegistry()
	collectors := metrics.NewCollectors(reg)
	sim := workload.NewSimulator(nil)
	return New(cfg, logger, collectors, sim, reg), collectors
}

func TestRootHandler(t *testing.T) {
	t.Parallel()

	srv, _ := newTestServer(t)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rr := httptest.NewRecorder()

	srv.rootHandler(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rr.Code)
	}

	if got := rr.Header().Get("Content-Type"); got != "application/json; charset=utf-8" {
		t.Fatalf("unexpected content type: %q", got)
	}

	var payload struct {
		Service string `json:"service"`
		Status  string `json:"status"`
		Docs    string `json:"docs"`
		Work    string `json:"work"`
		Metrics string `json:"metrics"`
	}
	if err := json.Unmarshal(rr.Body.Bytes(), &payload); err != nil {
		t.Fatalf("failed to parse JSON response: %v", err)
	}

	if payload.Service != "toy-load" || payload.Status != "running" || payload.Work != "/work" || payload.Metrics != "/metrics" {
		t.Fatalf("unexpected payload: %+v", payload)
	}
}

func TestRootHandlerNotFound(t *testing.T) {
	t.Parallel()

	srv, _ := newTestServer(t)
	req := httptest.NewRequest(http.MethodGet, "/bad", nil)
	rr := httptest.NewRecorder()

	srv.rootHandler(rr, req)

	if rr.Code != http.StatusNotFound {
		t.Fatalf("expected status 404, got %d", rr.Code)
	}
}

func TestRootHandlerMethodNotAllowed(t *testing.T) {
	t.Parallel()

	srv, _ := newTestServer(t)
	req := httptest.NewRequest(http.MethodPost, "/", nil)
	rr := httptest.NewRecorder()

	srv.rootHandler(rr, req)

	if rr.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected status 405, got %d", rr.Code)
	}
	if got := rr.Header().Get("Allow"); got != http.MethodGet {
		t.Fatalf("unexpected Allow header: %q", got)
	}
}

func TestReadyHandler(t *testing.T) {
	t.Parallel()

	srv, _ := newTestServer(t)
	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rr := httptest.NewRecorder()

	srv.readyHandler(rr, req)
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503 before ready, got %d", rr.Code)
	}

	srv.ready.Store(true)
	rr = httptest.NewRecorder()
	srv.readyHandler(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected status 200 after ready, got %d", rr.Code)
	}
}

func TestWorkHandlerMetrics(t *testing.T) {
	t.Parallel()

	srv, collectors := newTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/work?cpu_ms=1&sleep_ms=0&jitter_ms=0", nil)
	rr := httptest.NewRecorder()

	srv.workHandler(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rr.Code)
	}

	if got := testutil.ToFloat64(collectors.RequestCounter.WithLabelValues(http.MethodGet, "/work", "200")); got != 1 {
		t.Fatalf("unexpected request counter: %v", got)
	}

	if got := testutil.ToFloat64(collectors.InFlight); got != 0 {
		t.Fatalf("expected in-flight gauge reset, got %v", got)
	}
}

func TestWorkHandlerBadRequest(t *testing.T) {
	t.Parallel()

	srv, collectors := newTestServer(t)

	req := httptest.NewRequest(http.MethodGet, "/work?cpu_ms=bad", nil)
	rr := httptest.NewRecorder()

	srv.workHandler(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", rr.Code)
	}

	if got := testutil.ToFloat64(collectors.ErrorCounter.WithLabelValues("/work", "bad_request")); got != 1 {
		t.Fatalf("unexpected bad_request counter: %v", got)
	}
}

func TestWorkHandlerMethodNotAllowed(t *testing.T) {
	t.Parallel()

	srv, _ := newTestServer(t)
	req := httptest.NewRequest(http.MethodPost, "/work", nil)
	rr := httptest.NewRecorder()

	srv.workHandler(rr, req)

	if rr.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected status 405, got %d", rr.Code)
	}
}

func TestWorkHandlerErrorRate(t *testing.T) {
	t.Parallel()

	srv, collectors := newTestServer(t)
	req := httptest.NewRequest(http.MethodGet, "/work?err_rate=1", nil)
	rr := httptest.NewRecorder()

	srv.workHandler(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d", rr.Code)
	}
	if got := testutil.ToFloat64(collectors.ErrorCounter.WithLabelValues("/work", "err_rate")); got != 1 {
		t.Fatalf("unexpected err_rate counter: %v", got)
	}
}
