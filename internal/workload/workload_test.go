package workload

import (
	"net/url"
	"testing"
)

func TestParseParamsDefaults(t *testing.T) {
	params, err := ParseParams(url.Values{})
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
	params, err := ParseParams(values)
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

func TestParseParamsInvalidFormat(t *testing.T) {
	_, err := ParseParams(url.Values{"cpu_ms": []string{"bad"}})
	if err == nil {
		t.Fatal("expected error for invalid integer")
	}
	_, err = ParseParams(url.Values{"err_rate": []string{"-1"}})
	if err == nil {
		t.Fatal("expected error for invalid err_rate")
	}
}
