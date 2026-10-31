package main

import (
	"log"
	"time"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/config"
	store "github.com/ThanhNguyxnOrg/judgeloom-worker/internal/package"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}
	client := api.NewClient(cfg.APIURL, cfg.JudgeToken, nil)
	cache := &store.Store{Root: cfg.CacheDir}
	if err := cache.Cleanup(72 * time.Hour); err != nil {
		log.Printf("package cache cleanup failed: %v", err)
	}
	log.Printf("JudgeLoom worker %s configured for %s (client %T)", cfg.JudgeName, cfg.APIURL, client)
}
