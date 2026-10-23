"""Reject oversized or compressed JSON before routing or model validation."""

from starlette.responses import JSONResponse

MAX_BODY_BYTES = 64 * 1024


class RequestLimitsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope["headers"]}
        status, detail = None, None
        declared = headers.get(b"content-length")
        if declared is not None and (not declared.isdigit() or len(declared) > 10):
            status, detail = 400, "Invalid request size."
        elif declared and int(declared) > MAX_BODY_BYTES:
            status, detail = 413, "Request is too large."
        elif headers.get(b"content-encoding", b"identity").lower() not in (
            b"identity",
            b"",
        ):
            status, detail = 415, "Compressed request bodies are not accepted."
        parts, size = [], 0
        while status is None:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            part = message.get("body", b"")
            size += len(part)
            if size > MAX_BODY_BYTES:
                status, detail = 413, "Request is too large."
                break
            parts.append(part)
            if not message.get("more_body", False):
                break
        if status:
            return await JSONResponse(
                {"detail": detail},
                status_code=status,
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send)
        body, replayed = b"".join(parts), False

        async def replay():
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)
