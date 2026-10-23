"""Bounded HTTPS reads of reviewed listing providers, including every redirect.

The network backend resolves once, rejects non-public addresses and connects to
the validated address. HTTPCore retains the original host for TLS verification
and connection pooling, so a second DNS lookup cannot change the destination.
"""

import asyncio
from contextlib import contextmanager
import ipaddress
import socket
import ssl
import time
import zlib

import certifi
import httpcore
import httpx

SOURCE_HOSTS = frozenset(
    {
        "api.smartrecruiters.com",
        "boards-api.greenhouse.io",
        "careers.anglogoldashanti.com",
        "www.ghanacurrentjobs.com",
        "hiregh.com",
        "www.glmis.gov.gh",
        "jobs.newmont.com",
        "telecel.zohorecruit.com",
        "api.ashbyhq.com",
        "gh.fido.money",
        "erp.mpharma.com",
        "scholarships.gov.gh",
        "www.daad-ghana.org",
        "rid.ug.edu.gh",
        "ogr.knust.edu.gh",
        "www.povertyactionlab.org",
        "jobwebghana.com",
        "careers.votex365.com",
        "www.ug.edu.gh",
        "nya.gov.gh",
        "nap.nya.gov.gh",
        "careers.marriott.com",
        "www.lincoln.ac.uk",
        "loebfellowship.gsd.harvard.edu",
        "www.bodleian.ox.ac.uk",
        "italianacademy.columbia.edu",
        "www.unesco.org",
        "www.ucl.ac.uk",
        "www.lse.ac.uk",
    }
)


def source_url(value):
    raw = str(value)
    if len(raw) > 4096 or any(ord(c) < 33 for c in raw) or "\\" in raw:
        raise ValueError("Invalid source URL")
    try:
        url = httpx.URL(raw)
    except httpx.InvalidURL as error:
        raise ValueError("Invalid source URL") from error
    if (
        url.scheme != "https"
        or url.host not in SOURCE_HOSTS
        or url.port not in (None, 443)
        or url.userinfo
        or url.fragment
    ):
        raise ValueError("Unapproved source destination")
    return url


def public_address(value):
    address = ipaddress.ip_address(value)
    # Translation/tunnelling addresses can conceal a private IPv4 destination.
    if isinstance(address, ipaddress.IPv6Address) and (
        address.ipv4_mapped
        or address.sixtofour
        or address.teredo
        or address in ipaddress.ip_network("64:ff9b::/96")
        or address in ipaddress.ip_network("64:ff9b:1::/48")
    ):
        return False
    return address.is_global and not address.is_multicast


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        if host not in SOURCE_HOSTS or port != 443:
            raise httpcore.ConnectError("Unapproved source destination")
        started = time.monotonic()
        try:
            records = await asyncio.wait_for(
                asyncio.get_running_loop().getaddrinfo(
                    host, port, type=socket.SOCK_STREAM
                ),
                timeout=timeout or 10,
            )
        except TimeoutError as error:
            raise httpcore.ConnectTimeout("Source DNS timed out") from error
        except OSError as error:
            raise httpcore.ConnectError("Source DNS unavailable") from error
        addresses = list(dict.fromkeys(record[4][0] for record in records))
        if not addresses or any(not public_address(address) for address in addresses):
            raise httpcore.ConnectError("Source resolved to a non-public address")
        addresses.sort(key=lambda address: ipaddress.ip_address(address).version)
        last_error = None
        for address in addresses[:3]:
            remaining = (
                None if timeout is None else timeout - (time.monotonic() - started)
            )
            if remaining is not None and remaining <= 0:
                raise httpcore.ConnectTimeout("Source connection timed out")
            try:
                return await self.backend.connect_tcp(
                    address, port, remaining, local_address, socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                last_error = error
        raise last_error

    async def sleep(self, seconds):
        await self.backend.sleep(seconds)


@contextmanager
def network_errors():
    try:
        yield
    except (
        httpcore.TimeoutException,
        httpcore.NetworkError,
        httpcore.ProtocolError,
        httpcore.ProxyError,
        httpcore.UnsupportedProtocol,
    ) as error:
        kind = getattr(httpx, type(error).__name__, httpx.TransportError)
        raise kind("Public source request failed") from error


class SourceStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        with network_errors():
            async for part in self.stream:
                yield part

    async def aclose(self):
        with network_errors():
            await self.stream.aclose()


class SourceTransport(httpx.AsyncBaseTransport):
    def __init__(self, network_backend=None):
        self.pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(cafile=certifi.where()),
            max_connections=24,
            max_keepalive_connections=20,
            network_backend=network_backend or PublicNetworkBackend(),
        )

    async def handle_async_request(self, request):
        source_url(request.url)
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with network_errors():
            response = await self.pool.handle_async_request(core_request)
        return httpx.Response(
            response.status,
            headers=response.headers,
            stream=SourceStream(response.stream),
            extensions=response.extensions,
        )

    async def aclose(self):
        await self.pool.aclose()


class PublicSourceClient:
    def __init__(self, client, max_bytes=8 * 1024 * 1024):
        self.client = client
        self.max_bytes = max_bytes
        self.slots = asyncio.Semaphore(24)
        self.hosts = {}

    async def get(self, url, **kwargs):
        target = source_url(url)
        limit = self.hosts.setdefault(target.host, asyncio.Semaphore(3))
        async with limit, self.slots:
            for attempt in range(2):
                try:
                    response = await self._get(target, **kwargs)
                    if response.status_code not in (502, 503, 504) or attempt:
                        return response
                except (httpx.ConnectError, httpx.TimeoutException):
                    if attempt:
                        raise
                await asyncio.sleep(0.5)

    async def _get(self, url, **kwargs):
        for hop in range(6):
            async with self.client.stream(
                "GET", url, follow_redirects=False, **kwargs
            ) as response:
                if response.is_redirect:
                    if hop == 5 or "location" not in response.headers:
                        raise ValueError("Source redirect limit exceeded")
                    destination = source_url(
                        response.url.join(response.headers["location"])
                    )
                    if destination.host != url.host:
                        raise ValueError("Source redirected to another host")
                    url = destination
                    kwargs.pop("params", None)
                    continue
                length = response.headers.get("content-length", "")
                if length.isdigit() and int(length) > self.max_bytes:
                    raise ValueError("Source response is too large")
                encoding = response.headers.get("content-encoding", "identity").lower()
                if encoding not in {"identity", "gzip", "deflate"}:
                    raise ValueError("Unsupported source encoding")
                decoder = (
                    None
                    if encoding == "identity"
                    else zlib.decompressobj(31 if encoding == "gzip" else 15)
                )
                parts, size, raw_size = [], 0, 0
                async for raw in response.aiter_raw():
                    raw_size += len(raw)
                    if raw_size > self.max_bytes:
                        raise ValueError("Source response is too large")
                    try:
                        part = (
                            decoder.decompress(raw, self.max_bytes - size + 1)
                            if decoder
                            else raw
                        )
                    except zlib.error as error:
                        raise ValueError("Invalid source encoding") from error
                    size += len(part)
                    if size > self.max_bytes or decoder and decoder.unconsumed_tail:
                        raise ValueError("Source response is too large")
                    parts.append(part)
                if decoder and (not decoder.eof or decoder.unused_data):
                    raise ValueError("Incomplete source encoding")
                await response.aclose()
                return httpx.Response(
                    response.status_code,
                    headers={
                        k: v
                        for k, v in response.headers.items()
                        if k.lower()
                        not in {"content-encoding", "content-length", "set-cookie"}
                    },
                    content=b"".join(parts),
                    request=response.request,
                    extensions=response.extensions,
                )


def source_client(headers, timeout=12):
    return httpx.AsyncClient(
        transport=SourceTransport(),
        timeout=timeout,
        headers={**headers, "Accept-Encoding": "identity"},
        follow_redirects=False,
        trust_env=False,
    )
