"""Entry point: python -m crawler.rate_limiter [test URL | config]"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "config"

    if cmd == "config":
        from crawler.rate_limiter.limiter import RateLimiter
        limiter = RateLimiter()
        config = limiter._config
        print("\n=== Domain Configuration ===\n")
        print(f"Default RPS: {config['defaults']['requests_per_second']}")
        print(f"User-Agent:  {config['defaults']['user_agent']}")
        print(f"Backoff:     base={config['defaults']['backoff_base']}, max={config['defaults']['backoff_max']}s")
        print("\nPer-domain overrides:")
        for domain, cfg in config.get("domains", {}).items():
            rps = cfg.get("requests_per_second", "default")
            notes = cfg.get("notes", "")
            print(f"  {domain:<40s} rps={rps}  {notes}")

    elif cmd == "test":
        if len(args) < 2:
            print("Usage: python -m crawler.rate_limiter test <URL>")
            sys.exit(1)
        url = args[1]
        from crawler.rate_limiter.limiter import RateLimiter
        limiter = RateLimiter()
        allowed = limiter.is_allowed(url)
        print(f"\nURL: {url}")
        print(f"Allowed: {allowed}")
        if allowed:
            print("Calling wait()...")
            limiter.wait(url)
            print("Rate limit slot acquired.")
        print(f"\nLimiter stats: {limiter.get_stats()}")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python -m crawler.rate_limiter [test URL | config]")
        sys.exit(1)


if __name__ == "__main__":
    main()
