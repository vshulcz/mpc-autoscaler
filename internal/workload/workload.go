package workload

import (
	"context"
	"errors"
	"fmt"
	"math"
	"math/rand"
	"net/url"
	"strconv"
	"sync"
	"time"
)

const (
	maxCPUMillis     = 5000
	maxSleepMillis   = 5000
	maxJitterMillis  = 5000
	maxPayloadBytes  = 1 << 20
	defaultErrRate   = 0.0
	defaultCPUMillis = 0
	defaultSleepMs   = 0
	defaultJitterMs  = 0
	defaultPayload   = 0
)

// Params describes the workload knobs per request.
type Params struct {
	CPUMillis    int
	SleepMillis  int
	JitterMillis int
	ErrRate      float64
	PayloadBytes int
	ID           string
}

// Result captures outcomes of executing a workload.
type Result struct {
	JitterApplied int
	ShouldError   bool
}

// ParseParams validates and clamps query parameters into Params.
func ParseParams(values url.Values) (Params, error) {
	params := Params{
		CPUMillis:    defaultCPUMillis,
		SleepMillis:  defaultSleepMs,
		JitterMillis: defaultJitterMs,
		ErrRate:      defaultErrRate,
		PayloadBytes: defaultPayload,
		ID:           values.Get("id"),
	}

	var err error
	if params.CPUMillis, err = parseBoundedInt(values.Get("cpu_ms"), 0, maxCPUMillis, defaultCPUMillis); err != nil {
		return Params{}, fmt.Errorf("cpu_ms: %w", err)
	}
	if params.SleepMillis, err = parseBoundedInt(values.Get("sleep_ms"), 0, maxSleepMillis, defaultSleepMs); err != nil {
		return Params{}, fmt.Errorf("sleep_ms: %w", err)
	}
	if params.JitterMillis, err = parseBoundedInt(values.Get("jitter_ms"), 0, maxJitterMillis, defaultJitterMs); err != nil {
		return Params{}, fmt.Errorf("jitter_ms: %w", err)
	}
	if params.PayloadBytes, err = parseBoundedInt(values.Get("payload_bytes"), 0, maxPayloadBytes, defaultPayload); err != nil {
		return Params{}, fmt.Errorf("payload_bytes: %w", err)
	}

	if v := values.Get("err_rate"); v != "" {
		f, parseErr := strconv.ParseFloat(v, 64)
		if parseErr != nil {
			return Params{}, fmt.Errorf("err_rate: %w", parseErr)
		}
		if f < 0 || f > 1 {
			return Params{}, errors.New("value must be between 0 and 1")
		}
		params.ErrRate = f
	}

	return params, nil
}

func parseBoundedInt(raw string, min, max, def int) (int, error) {
	if raw == "" {
		return def, nil
	}
	val, err := strconv.Atoi(raw)
	if err != nil {
		return 0, err
	}
	if val < min {
		return min, nil
	}
	if val > max {
		return max, nil
	}
	return val, nil
}

// Simulator executes workloads with deterministic jitter/error sampling per instance.
type Simulator struct {
	rand *rand.Rand
	mu   sync.Mutex
}

// NewSimulator builds a simulator with the provided source or a seeded default.
func NewSimulator(src rand.Source) *Simulator {
	if src == nil {
		src = rand.NewSource(time.Now().UnixNano())
	}
	return &Simulator{
		rand: rand.New(src),
	}
}

// Execute applies CPU burn, sleep, jitter, and error sampling.
func (s *Simulator) Execute(ctx context.Context, params Params) Result {
	busyFor(ctx, params.CPUMillis)
	sleep(ctx, params.SleepMillis)
	jitter := sleepJitter(ctx, params.JitterMillis, s.randomIntn)
	return Result{
		JitterApplied: jitter,
		ShouldError:   s.shouldError(params.ErrRate),
	}
}

func busyFor(ctx context.Context, millis int) {
	if millis <= 0 {
		return
	}
	deadline := time.Now().Add(time.Duration(millis) * time.Millisecond)
	var x float64
	for time.Now().Before(deadline) {
		select {
		case <-ctx.Done():
			return
		default:
		}
		x += math.Pi
		if x > 1e9 {
			x = 0
		}
	}
}

func sleep(ctx context.Context, millis int) {
	if millis <= 0 {
		return
	}
	timer := time.NewTimer(time.Duration(millis) * time.Millisecond)
	defer timer.Stop()
	select {
	case <-ctx.Done():
	case <-timer.C:
	}
}

func sleepJitter(ctx context.Context, maxMillis int, rng func(int) int) int {
	if maxMillis <= 0 {
		return 0
	}
	jitter := rng(maxMillis)
	sleep(ctx, jitter)
	return jitter
}

func (s *Simulator) shouldError(rate float64) bool {
	if rate <= 0 {
		return false
	}
	if rate >= 1 {
		return true
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.rand.Float64() < rate
}

func (s *Simulator) randomIntn(n int) int {
	if n <= 0 {
		return 0
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.rand.Intn(n)
}
