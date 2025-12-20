package httpserver

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/testutil"

	"github.com/vshulcz/mpc-autoscaler/internal/config"
	"github.com/vshulcz/mpc-autoscaler/internal/metrics"
	"github.com/vshulcz/mpc-autoscaler/internal/workload"
)

func TestWorkHandlerMetrics(t *testing.T) {
	cfg := config.Config{
		MetricsPath: "/metrics",
	}
	logger := slog.New(slog.NewTextHandler(io.Discard, &slog.HandlerOptions{Level: slog.LevelDebug}))
	reg := prometheus.NewRegistry()
	collectors := metrics.NewCollectors(reg)
	sim := workload.NewSimulator(nil)
	srv := New(cfg, logger, collectors, sim, reg)

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
