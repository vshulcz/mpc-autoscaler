package httpserver

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/vshulcz/mpc-autoscaler/toy-load/internal/config"
	"github.com/vshulcz/mpc-autoscaler/toy-load/internal/metrics"
	"github.com/vshulcz/mpc-autoscaler/toy-load/internal/workload"
)

// Server wraps the http.Server and handler state.
type Server struct {
	cfg     config.Config
	logger  *slog.Logger
	metrics *metrics.Collectors
	sim     *workload.Simulator
	server  *http.Server
	ready   atomic.Bool
}

type rootResponse struct {
	Service string `json:"service"`
	Status  string `json:"status"`
	Docs    string `json:"docs"`
	Work    string `json:"work"`
	Metrics string `json:"metrics"`
}

// New builds the HTTP server with handlers and middleware.
func New(cfg config.Config, logger *slog.Logger, collectors *metrics.Collectors, sim *workload.Simulator, gatherer prometheus.Gatherer) *Server {
	s := &Server{
		cfg:     cfg,
		logger:  logger,
		metrics: collectors,
		sim:     sim,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", s.rootHandler)
	mux.HandleFunc("/healthz", s.healthHandler)
	mux.HandleFunc("/readyz", s.readyHandler)
	mux.HandleFunc("/work", s.workHandler)
	mux.Handle(cfg.MetricsPath, promhttp.HandlerFor(gatherer, promhttp.HandlerOpts{}))

	s.server = &http.Server{
		Addr:           fmt.Sprintf(":%d", cfg.Port),
		Handler:        mux,
		ReadTimeout:    cfg.ReadTimeout,
		WriteTimeout:   cfg.WriteTimeout,
		IdleTimeout:    cfg.IdleTimeout,
		MaxHeaderBytes: cfg.MaxHeaderBytes,
	}

	return s
}

// Run starts the HTTP server and blocks until shutdown.
func (s *Server) Run(ctx context.Context) error {
	s.ready.Store(true)

	errCh := make(chan error, 1)
	go func() {
		s.logger.Info("server listening", "port", s.cfg.Port, "metrics_path", s.cfg.MetricsPath)
		if err := s.server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
			return
		}
		errCh <- nil
	}()

	select {
	case <-ctx.Done():
		s.ready.Store(false)
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		s.logger.Info("shutting down HTTP server")
		if err := s.server.Shutdown(shutdownCtx); err != nil {
			s.logger.Error("server shutdown failed", "error", err)
			return err
		}
		return <-errCh
	case err := <-errCh:
		return err
	}
}

func (s *Server) rootHandler(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	if !allowGet(w, r) {
		return
	}
	writeJSON(w, http.StatusOK, rootResponse{
		Service: "toy-load",
		Status:  "running",
		Docs:    "https://github.com/vshulcz/mpc-autoscaler",
		Work:    "/work",
		Metrics: s.cfg.MetricsPath,
	})
}

func (s *Server) healthHandler(w http.ResponseWriter, r *http.Request) {
	if !allowGet(w, r) {
		return
	}
	writePlain(w, http.StatusOK, "ok")
}

func (s *Server) readyHandler(w http.ResponseWriter, r *http.Request) {
	if !allowGet(w, r) {
		return
	}
	if !s.ready.Load() {
		writePlain(w, http.StatusServiceUnavailable, "not ready")
		return
	}
	writePlain(w, http.StatusOK, "ok")
}

func (s *Server) workHandler(w http.ResponseWriter, r *http.Request) {
	const path = "/work"
	if !allowGet(w, r) {
		return
	}
	start := time.Now()
	s.metrics.InFlight.Inc()
	defer s.metrics.InFlight.Dec()

	params, err := workload.ParseParams(r.URL.Query())
	if err != nil {
		s.metrics.ErrorCounter.WithLabelValues(path, "bad_request").Inc()
		s.observeRequest(r.Method, path, http.StatusBadRequest, start)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	result := s.sim.Execute(ctx, params)

	s.metrics.WorkCPU.Observe(float64(params.CPUMillis))
	s.metrics.WorkSleep.Observe(float64(params.SleepMillis))
	s.metrics.WorkJitter.Observe(float64(params.JitterMillis))

	status := http.StatusOK
	body := buildResponseBody(params)
	if result.ShouldError {
		status = http.StatusInternalServerError
		body = "error"
		s.metrics.ErrorCounter.WithLabelValues(path, "err_rate").Inc()
	}

	s.observeRequest(r.Method, path, status, start)
	writePlain(w, status, body)

	if logger := s.logger; logger != nil {
		logger.Debug("work request",
			"id", params.ID,
			"method", r.Method,
			"status", status,
			"duration_ms", time.Since(start).Milliseconds(),
			"cpu_ms", params.CPUMillis,
			"sleep_ms", params.SleepMillis,
			"jitter_ms", params.JitterMillis,
			"jitter_applied", result.JitterApplied,
			"payload_bytes", params.PayloadBytes,
			"err_rate", params.ErrRate,
		)
	}
}

func allowGet(w http.ResponseWriter, r *http.Request) bool {
	if r.Method == http.MethodGet {
		return true
	}
	w.Header().Set("Allow", http.MethodGet)
	http.Error(w, http.StatusText(http.StatusMethodNotAllowed), http.StatusMethodNotAllowed)
	return false
}

func (s *Server) observeRequest(method, path string, status int, start time.Time) {
	s.metrics.RequestDuration.WithLabelValues(method, path).Observe(time.Since(start).Seconds())
	s.metrics.RequestCounter.WithLabelValues(method, path, strconv.Itoa(status)).Inc()
}

func writePlain(w http.ResponseWriter, status int, body string) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	body, err := json.Marshal(payload)
	if err != nil {
		http.Error(w, http.StatusText(http.StatusInternalServerError), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func buildResponseBody(params workload.Params) string {
	if params.PayloadBytes <= 0 {
		return fmt.Sprintf("work: cpu_ms=%d sleep_ms=%d jitter_ms=%d",
			params.CPUMillis, params.SleepMillis, params.JitterMillis)
	}
	return strings.Repeat("a", params.PayloadBytes)
}
