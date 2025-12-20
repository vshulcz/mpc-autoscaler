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
	defaultWriteTimeout   = 10 * time.Second
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
		if !strings.HasPrefix(v, "/") {
			return Config{}, fmt.Errorf("METRICS_PATH must start with /")
		}
		cfg.MetricsPath = v
	}

	if v := getEnv("READ_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil {
			return Config{}, fmt.Errorf("invalid READ_TIMEOUT: %w", err)
		}
		cfg.ReadTimeout = d
	}

	if v := getEnv("WRITE_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil {
			return Config{}, fmt.Errorf("invalid WRITE_TIMEOUT: %w", err)
		}
		cfg.WriteTimeout = d
	}

	if v := getEnv("IDLE_TIMEOUT"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil {
			return Config{}, fmt.Errorf("invalid IDLE_TIMEOUT: %w", err)
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
		cfg.LogLevel = strings.ToLower(v)
	}

	if v := getEnv("APP_NAME"); v != "" {
		cfg.AppName = v
	}

	return cfg, nil
}

func getEnv(key string) string {
	return strings.TrimSpace(os.Getenv(key))
}
