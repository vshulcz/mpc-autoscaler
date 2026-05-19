package config

import (
	"testing"
	"time"
)

func clearEnv(t *testing.T) {
	t.Helper()
	for _, key := range []string{
		"PORT",
		"METRICS_PATH",
		"READ_TIMEOUT",
		"WRITE_TIMEOUT",
		"IDLE_TIMEOUT",
		"MAX_HEADER_BYTES",
		"LOG_LEVEL",
		"APP_NAME",
	} {
		t.Setenv(key, "")
	}
}

func TestLoadDefaults(t *testing.T) {
	clearEnv(t)

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.Port != defaultPort || cfg.MetricsPath != defaultMetricsPath || cfg.AppName != defaultAppName {
		t.Fatalf("unexpected defaults: %+v", cfg)
	}
	if cfg.ReadTimeout != defaultReadTimeout || cfg.WriteTimeout != defaultWriteTimeout || cfg.IdleTimeout != defaultIdleTimeout {
		t.Fatalf("unexpected timeout defaults: %+v", cfg)
	}
}

func TestLoadEnvOverrides(t *testing.T) {
	clearEnv(t)
	t.Setenv("PORT", "8080")
	t.Setenv("METRICS_PATH", "/custom-metrics")
	t.Setenv("READ_TIMEOUT", "2s")
	t.Setenv("WRITE_TIMEOUT", "3s")
	t.Setenv("IDLE_TIMEOUT", "4s")
	t.Setenv("MAX_HEADER_BYTES", "2048")
	t.Setenv("LOG_LEVEL", "DEBUG")
	t.Setenv("APP_NAME", "custom")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.Port != 8080 || cfg.MetricsPath != "/custom-metrics" || cfg.MaxHeaderBytes != 2048 {
		t.Fatalf("unexpected scalar config: %+v", cfg)
	}
	if cfg.ReadTimeout != 2*time.Second || cfg.WriteTimeout != 3*time.Second || cfg.IdleTimeout != 4*time.Second {
		t.Fatalf("unexpected timeout config: %+v", cfg)
	}
	if cfg.LogLevel != "debug" || cfg.AppName != "custom" {
		t.Fatalf("unexpected log/app config: %+v", cfg)
	}
}

func TestLoadRejectsInvalidValues(t *testing.T) {
	cases := []struct {
		name string
		key  string
		val  string
	}{
		{name: "bad port", key: "PORT", val: "70000"},
		{name: "bad metrics path", key: "METRICS_PATH", val: "metrics"},
		{name: "root metrics path", key: "METRICS_PATH", val: "/"},
		{name: "work metrics path", key: "METRICS_PATH", val: "/work"},
		{name: "health metrics path", key: "METRICS_PATH", val: "/healthz"},
		{name: "ready metrics path", key: "METRICS_PATH", val: "/readyz"},
		{name: "zero read timeout", key: "READ_TIMEOUT", val: "0s"},
		{name: "negative write timeout", key: "WRITE_TIMEOUT", val: "-1s"},
		{name: "bad idle timeout", key: "IDLE_TIMEOUT", val: "bad"},
		{name: "bad max header bytes", key: "MAX_HEADER_BYTES", val: "0"},
		{name: "bad log level", key: "LOG_LEVEL", val: "trace"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			clearEnv(t)
			t.Setenv(tc.key, tc.val)
			if _, err := Load(); err == nil {
				t.Fatal("expected error")
			}
		})
	}
}
