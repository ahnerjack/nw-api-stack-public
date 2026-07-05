# xapi-v1-wrapper

Systemd unit for the NW-API `/v1/*` policy wrapper.
Runtime secrets and endpoint values should stay in systemd drop-ins or environment files, not in git.

Recommended timeout layering:

- wrapper upstream total timeout: 540s
- wrapper stream idle timeout: 180s
- outer Caddy read/write timeout: 660s or higher

Example drop-in:

```ini
[Service]
Environment=XAPI_UPSTREAM=http://127.0.0.1:18066
Environment=XAPI_DATA_BASE=http://127.0.0.1:18066/xapi-data
Environment=XAPI_UPSTREAM_TIMEOUT_SECONDS=540
Environment=XAPI_STREAM_IDLE_TIMEOUT_SECONDS=180
Environment=XAPI_UPSTREAM_CONNECT_TIMEOUT_SECONDS=10
```

The wrapper performs a quick TCP check before proxying so a broken SSH tunnel returns `UPSTREAM_TUNNEL_DOWN` instead of hanging until the client times out.
