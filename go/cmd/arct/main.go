package main

import (
	"context"
	"os"
	"os/signal"

	"arct.cloud/sdk/go/internal/cli"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	os.Exit((&cli.App{}).Run(ctx, os.Args[1:]))
}
