package httpserver

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"runtime/debug"
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

// routePattern returns a low-cardinality label for HTTP metrics.
// Unknown paths collapse to "other" so we never explode cardinality
// on a misconfigured scraper or scanner.
func (s *Server) routePattern(rawPath string) string {
	switch rawPath {
	case "/", "/healthz", "/readyz", "/work":
		return rawPath
	}
	if rawPath == s.cfg.MetricsPath {
		return s.cfg.MetricsPath
	}
	return "other"
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

	handler := s.recoverMiddleware(s.observeMiddleware(mux))

	s.server = &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.Port),
		Handler:           handler,
		ReadTimeout:       cfg.ReadTimeout,
		ReadHeaderTimeout: cfg.ReadHeaderTimeout,
		WriteTimeout:      cfg.WriteTimeout,
		IdleTimeout:       cfg.IdleTimeout,
		MaxHeaderBytes:    cfg.MaxHeaderBytes,
	}

	return s
}

// Handler returns the fully-wrapped HTTP handler (recover + observe + mux).
// Exposed for integration tests so middleware behaviour is exercised.
func (s *Server) Handler() http.Handler {
	return s.server.Handler
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
		shutdownCtx, cancel := context.WithTimeout(context.Background(), s.cfg.ShutdownTimeout)
		defer cancel()
		s.logger.Info("shutting down HTTP server", "timeout", s.cfg.ShutdownTimeout)
		if err := s.server.Shutdown(shutdownCtx); err != nil {
			s.logger.Error("server shutdown failed", "error", err)
			return err
		}
		return <-errCh
	case err := <-errCh:
		return err
	}
}

// statusRecorder captures the response status code for metrics middleware.
// It also records bytes written if downstream wants to add a size histogram.
type statusRecorder struct {
	http.ResponseWriter
	status      int
	wroteHeader bool
}

func (r *statusRecorder) WriteHeader(code int) {
	if r.wroteHeader {
		return
	}
	r.status = code
	r.wroteHeader = true
	r.ResponseWriter.WriteHeader(code)
}

func (r *statusRecorder) Write(b []byte) (int, error) {
	if !r.wroteHeader {
		r.WriteHeader(http.StatusOK)
	}
	return r.ResponseWriter.Write(b)
}

// observeMiddleware records request duration and counter for every route.
// Without this middleware, request metrics covered only /work, which made
// dashboards under-report scraper, health and 404/405 traffic.
func (s *Server) observeMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r)
		path := s.routePattern(r.URL.Path)
		s.metrics.RequestDuration.WithLabelValues(r.Method, path).Observe(time.Since(start).Seconds())
		s.metrics.RequestCounter.WithLabelValues(r.Method, path, strconv.Itoa(rec.status)).Inc()
	})
}

// recoverMiddleware turns handler panics into structured 500 responses,
// keeping connection accounting and metrics consistent. Without it a
// panic closes the connection abruptly and bypasses both metrics and logs.
func (s *Server) recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			rec := recover()
			if rec == nil {
				return
			}
			path := s.routePattern(r.URL.Path)
			s.metrics.PanicCounter.WithLabelValues(path).Inc()
			s.logger.Error("handler panic",
				"method", r.Method,
				"path", path,
				"panic", fmt.Sprintf("%v", rec),
				"stack", string(debug.Stack()),
			)
			// Best-effort: only write if no body yet.
			http.Error(w, http.StatusText(http.StatusInternalServerError), http.StatusInternalServerError)
		}()
		next.ServeHTTP(w, r)
	})
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

	params, err := workload.ParseParams(r.URL.Query(), s.cfg.MaxQueryIDBytes)
	if err != nil {
		s.metrics.ErrorCounter.WithLabelValues(path, "bad_request").Inc()
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	result := s.sim.Execute(ctx, params)

	s.metrics.WorkCPU.Observe(float64(params.CPUMillis) / 1000.0)
	s.metrics.WorkSleep.Observe(float64(params.SleepMillis) / 1000.0)
	s.metrics.WorkJitter.Observe(float64(params.JitterMillis) / 1000.0)

	status := http.StatusOK
	body := buildResponseBody(params)
	if result.ShouldError {
		status = http.StatusInternalServerError
		body = "error"
		s.metrics.ErrorCounter.WithLabelValues(path, "err_rate").Inc()
	}

	writePlain(w, status, body)

	if logger := s.logger; logger != nil {
		logger.Debug("work request",
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
