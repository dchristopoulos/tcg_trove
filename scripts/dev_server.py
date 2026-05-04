import argparse
import socket
import sys
from pathlib import Path

import uvicorn

# Ensure `app` is importable when this script is run as `python scripts/dev_server.py`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def _find_free_port(host: str, start_port: int, max_tries: int = 30) -> int | None:
    for offset in range(max_tries):
        candidate = start_port + offset
        if not _port_is_open(host, candidate):
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description='Run TCG Trove dev server with reliable port fallback.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload during development.')
    args = parser.parse_args()

    target_port = args.port
    if _port_is_open(args.host, target_port):
        fallback = _find_free_port(args.host, target_port + 1)
        if fallback is None:
            print('No free port found in scan range. Stop other servers and retry.', file=sys.stderr)
            return 1
        print(f'Port {target_port} is busy. Falling back to {fallback}.')
        target_port = fallback

    print(f'Starting TCG Trove on http://{args.host}:{target_port} (reload={args.reload})')

    uvicorn.run('app.main:app', host=args.host, port=target_port, reload=args.reload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
