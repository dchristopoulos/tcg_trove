from collections import Counter
from threading import Lock

_metric_lock = Lock()
_request_total = 0
_requests_by_status = Counter()
_requests_by_path = Counter()
_requests_by_method = Counter()
_message_replies_total = 0
_message_poll_total = 0


def record_request(*, method: str, path: str, status_code: int) -> None:
    global _request_total
    with _metric_lock:
        _request_total += 1
        _requests_by_status[str(status_code)] += 1
        _requests_by_path[path] += 1
        _requests_by_method[method.upper()] += 1


def render_prometheus_metrics() -> str:
    lines: list[str] = [
        '# HELP tcg_trove_http_requests_total Total HTTP requests seen by the app.',
        '# TYPE tcg_trove_http_requests_total counter',
        f'tcg_trove_http_requests_total {_request_total}',
        '# HELP tcg_trove_http_requests_by_status_total Requests grouped by status code.',
        '# TYPE tcg_trove_http_requests_by_status_total counter',
    ]

    for status, count in sorted(_requests_by_status.items()):
        lines.append(f'tcg_trove_http_requests_by_status_total{{status="{status}"}} {count}')

    lines.extend(
        [
            '# HELP tcg_trove_http_requests_by_method_total Requests grouped by HTTP method.',
            '# TYPE tcg_trove_http_requests_by_method_total counter',
        ]
    )
    for method, count in sorted(_requests_by_method.items()):
        lines.append(f'tcg_trove_http_requests_by_method_total{{method="{method}"}} {count}')

    lines.extend(
        [
            '# HELP tcg_trove_http_requests_by_path_total Requests grouped by request path.',
            '# TYPE tcg_trove_http_requests_by_path_total counter',
        ]
    )
    for path, count in sorted(_requests_by_path.items()):
        safe_path = path.replace('"', "'")
        lines.append(f'tcg_trove_http_requests_by_path_total{{path="{safe_path}"}} {count}')

    lines.extend(
        [
            '# HELP tcg_trove_message_replies_total Total message replies created.',
            '# TYPE tcg_trove_message_replies_total counter',
            f'tcg_trove_message_replies_total {_message_replies_total}',
            '# HELP tcg_trove_message_poll_total Total message poll requests served.',
            '# TYPE tcg_trove_message_poll_total counter',
            f'tcg_trove_message_poll_total {_message_poll_total}',
        ]
    )

    return '\n'.join(lines) + '\n'


def record_message_reply() -> None:
    global _message_replies_total
    with _metric_lock:
        _message_replies_total += 1


def record_message_poll() -> None:
    global _message_poll_total
    with _metric_lock:
        _message_poll_total += 1
