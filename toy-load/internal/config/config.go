package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config captures runtime configuration driven by environment variables.
type Config struct {
	Port           int
	MetricsPath    string
	ReadTimeout    time.Duration
	WriteTimeout   time.Duration
	IdleTimeout    time.Duration
	MaxHeaderBytes int
	LogLevel       string
	AppName        string
}

const (
	defaultPort           = 9090
	defaultMetricsPath    = "/metrics"
	defaultReadTimeout    = 5 * time.Second
	defaultWriteTimeout   = 20 * time.Second
	defaultIdleTimeout    = 60 * time.Second
	defaultMaxHeaderBytes = 1 << 20
	defaultLogLevel       = "info"
	defaultAppName        = "toy-load"
)

// Load reads configuration from the environment.
func Load() (Config, error) {
	cfg := Config{
		Port:           defaultPort,
		MetricsPath:    defaultMetricsPath,
		ReadTimeout:    defaultReadTimeout,
		WriteTimeout:   defaultWriteTimeout,
		IdleTimeout:    defaultIdleTimeout,
		MaxHeaderBytes: defaultMaxHeaderBytes,
		LogLevel:       defaultLogLevel,
		AppName:        defaultAppName,
	}

	if v := getEnv("PORT"); v != "" {
		port, err := strconv.Atoi(v)
		if err != nil || port <= 0 || port > 65535 {
			return Config{}, fmt.Errorf("invalid PORT value: %q", v)
		}
		cfg.Port = port
	}

	if v := getEnv("METRICS_PATH"); v != "" {
		if err := validateMetricsPath(v); err != nil {
			return Config{}, err
		}
		cfg.MetricsPath = v
	}

	if v := getEnv("READ_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil {
			return Config{}, fmt.Errorf("invalid READ_TIMEOUT: %w", err)
		}
		if d <= 0 {
			return Config{}, fmt.Errorf("READ_TIMEOUT must be > 0")
		}
		cfg.ReadTimeout = d
	}

	if v := getEnv("WRITE_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil {
			return Config{}, fmt.Errorf("invalid WRITE_TIMEOUT: %w", err)
		}
		if d <= 0 {
			return Config{}, fmt.Errorf("WRITE_TIMEOUT must be > 0")
		}
		cfg.WriteTimeout = d
	}

	if v := getEnv("IDLE_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil {
			return Config{}, fmt.Errorf("invalid IDLE_TIMEOUT: %w", err)
		}
		if d <= 0 {
			return Config{}, fmt.Errorf("IDLE_TIMEOUT must be > 0")
		}
		cfg.IdleTimeout = d
	}

	if v := getEnv("MAX_HEADER_BYTES"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return Config{}, fmt.Errorf("invalid MAX_HEADER_BYTES: %q", v)
		}
		cfg.MaxHeaderBytes = n
	}

	if v := getEnv("LOG_LEVEL"); v != "" {
		level := strings.ToLower(v)
		switch level {
		case "debug", "info", "warn", "warning", "error":
			cfg.LogLevel = level
		default:
			return Config{}, fmt.Errorf("invalid LOG_LEVEL value: %q", v)
		}
	}

	if v := getEnv("APP_NAME"); v != "" {
		cfg.AppName = v
	}

	return cfg, nil
}

func getEnv(key string) string {
	return strings.TrimSpace(os.Getenv(key))
}

func validateMetricsPath(path string) error {
	if !strings.HasPrefix(path, "/") {
		return fmt.Errorf("METRICS_PATH must start with /")
	}

	switch path {
	case "/", "/healthz", "/readyz", "/work":
		return fmt.Errorf("METRICS_PATH conflicts with built-in endpoint %q", path)
	}

	return nil
}
