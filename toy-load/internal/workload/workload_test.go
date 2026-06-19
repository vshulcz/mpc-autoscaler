package workload

import (
	"context"
	"math/rand"
	"net/url"
	"testing"
)

func TestParseParamsDefaults(t *testing.T) {
	params, err := ParseParams(url.Values{}, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if params.CPUMillis != 0 || params.SleepMillis != 0 || params.JitterMillis != 0 || params.ErrRate != 0 {
		t.Fatalf("unexpected defaults: %+v", params)
	}
}

func TestParseParamsClamps(t *testing.T) {
	values := url.Values{
		"cpu_ms":        []string{"6000"},
		"sleep_ms":      []string{"-10"},
		"jitter_ms":     []string{"9999"},
		"payload_bytes": []string{"2000000"},
	}
	params, err := ParseParams(values, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if params.CPUMillis != maxCPUMillis {
		t.Fatalf("expected cpu clamp to %d, got %d", maxCPUMillis, params.CPUMillis)
	}
	if params.SleepMillis != 0 {
		t.Fatalf("expected sleep clamp to 0, got %d", params.SleepMillis)
	}
	if params.JitterMillis != maxJitterMillis {
		t.Fatalf("expected jitter clamp, got %d", params.JitterMillis)
	}
	if params.PayloadBytes != maxPayloadBytes {
		t.Fatalf("expected payload clamp, got %d", params.PayloadBytes)
	}
}

func TestParseParamsOptionalFields(t *testing.T) {
	values := url.Values{
		"id":            []string{"req-1"},
		"payload_bytes": []string{"128"},
		"err_rate":      []string{"0.25"},
	}

	params, err := ParseParams(values, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if params.ID != "req-1" || params.PayloadBytes != 128 || params.ErrRate != 0.25 {
		t.Fatalf("unexpected optional fields: %+v", params)
	}
}

func TestParseParamsInvalidFormat(t *testing.T) {
	_, err := ParseParams(url.Values{"cpu_ms": []string{"bad"}}, 0)
	if err == nil {
		t.Fatal("expected error for invalid integer")
	}
	_, err = ParseParams(url.Values{"err_rate": []string{"-1"}}, 0)
	if err == nil {
		t.Fatal("expected error for invalid err_rate")
	}
}

func TestSimulatorErrorRateEdges(t *testing.T) {
	sim := NewSimulator(rand.NewSource(1))
	ctx := context.Background()

	if sim.Execute(ctx, Params{ErrRate: 0}).ShouldError {
		t.Fatal("err_rate=0 must not error")
	}
	if !sim.Execute(ctx, Params{ErrRate: 1}).ShouldError {
		t.Fatal("err_rate=1 must error")
	}
}

func TestSleepJitterUsesSamplerAndHonorsCanceledContext(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	got := sleepJitter(ctx, 10, func(n int) int {
		if n != 10 {
			t.Fatalf("unexpected jitter bound: %d", n)
		}
		return 7
	})

	if got != 7 {
		t.Fatalf("expected sampled jitter 7, got %d", got)
	}
}

func TestExecuteReturnsAppliedJitter(t *testing.T) {
	sim := NewSimulator(rand.NewSource(1))
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	result := sim.Execute(ctx, Params{JitterMillis: 10})
	if result.JitterApplied < 0 || result.JitterApplied >= 10 {
		t.Fatalf("unexpected jitter: %d", result.JitterApplied)
	}
}
