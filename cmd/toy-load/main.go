package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/prometheus/client_golang/prometheus"

	"github.com/vshulcz/mpc-autoscaler/internal/config"
	"github.com/vshulcz/mpc-autoscaler/internal/httpserver"
	"github.com/vshulcz/mpc-autoscaler/internal/logging"
	"github.com/vshulcz/mpc-autoscaler/internal/metrics"
	"github.com/vshulcz/mpc-autoscaler/internal/workload"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	logger := logging.New(cfg.LogLevel, cfg.AppName)
	logger.Info("starting toy-load", "config", cfg)

	reg := prometheus.NewRegistry()
	collectors := metrics.NewCollectors(reg)
	sim := workload.NewSimulator(nil)
	server := httpserver.New(cfg, logger, collectors, sim, reg)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := server.Run(ctx); err != nil {
		if err == context.Canceled {
			logger.Warn("server context canceled")
		} else {
			logger.Error("server error", "error", err)
			os.Exit(1)
		}
	}

	logger.Info("toy-load exited cleanly")
}
