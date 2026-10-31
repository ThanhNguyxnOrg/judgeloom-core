package main

import (
	"log"

	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/api"
	"github.com/ThanhNguyxnOrg/judgeloom-worker/internal/config"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}
	client := api.NewClient(cfg.APIURL, cfg.JudgeToken, nil)
	log.Printf("JudgeLoom worker %s configured for %s (client %T)", cfg.JudgeName, cfg.APIURL, client)
}
