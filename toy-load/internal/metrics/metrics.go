package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
)

// Collectors bundles all custom collectors for the service.
type Collectors struct {
	RequestCounter  *prometheus.CounterVec
	RequestDuration *prometheus.HistogramVec
	InFlight        prometheus.Gauge
	WorkCPU         prometheus.Histogram
	WorkSleep       prometheus.Histogram
	WorkJitter      prometheus.Histogram
	ErrorCounter    *prometheus.CounterVec
	PanicCounter    *prometheus.CounterVec
}

// NewCollectors registers collectors on the provided registerer.
func NewCollectors(reg prometheus.Registerer) *Collectors {
	c := &Collectors{
		RequestCounter: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "toy_http_requests_total",
				Help: "Total HTTP requests processed by toy-load.",
			},
			[]string{"method", "path", "code"},
		),
		RequestDuration: prometheus.NewHistogramVec(
			prometheus.HistogramOpts{
				Name: "toy_http_request_duration_seconds",
				Help: "Histogram of request durations in seconds.",
				// Buckets reach 30s to cover worst-case /work
				// (cpu_ms + sleep_ms + jitter_ms <= 15s) plus margin
				// for graceful-shutdown windows. Lower buckets keep
				// p50/p95 resolution on healthy traffic.
				Buckets: []float64{
					0.001, 0.002, 0.005,
					0.01, 0.02, 0.05,
					0.1, 0.2, 0.5,
					1, 2, 5, 10, 15, 20, 30,
				},
			},
			[]string{"method", "path"},
		),
		InFlight: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "toy_in_flight_requests",
			Help: "Number of in-flight requests.",
		}),
		WorkCPU: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "toy_work_cpu_seconds",
			Help:    "Histogram of requested CPU work in seconds.",
			Buckets: workBuckets(),
		}),
		WorkSleep: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "toy_work_sleep_seconds",
			Help:    "Histogram of requested sleep duration in seconds.",
			Buckets: workBuckets(),
		}),
		WorkJitter: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "toy_work_jitter_seconds",
			Help:    "Histogram of requested jitter bounds in seconds.",
			Buckets: workBuckets(),
		}),
		PanicCounter: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "toy_panics_total",
				Help: "Total recovered handler panics by route.",
			},
			[]string{"path"},
		),
		ErrorCounter: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "toy_errors_total",
				Help: "Total toy-load errors by reason.",
			},
			[]string{"path", "reason"},
		),
	}

	reg.MustRegister(
		c.RequestCounter,
		c.RequestDuration,
		c.InFlight,
		c.WorkCPU,
		c.WorkSleep,
		c.WorkJitter,
		c.ErrorCounter,
		c.PanicCounter,
		prometheus.NewGoCollector(),
		prometheus.NewProcessCollector(prometheus.ProcessCollectorOpts{}),
	)

	return c
}

// workBuckets covers work parameters in seconds (1ms .. 5s).
func workBuckets() []float64 {
	return []float64{0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5}
}
