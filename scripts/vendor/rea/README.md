# REA extraction

This directory contains a deliberately small, dependency-free extraction from the owner-supplied REA 6.7.0 archive, whose package metadata names `https://github.com/morluto/rea` as its upstream repository. No claim is made that the archive was compared byte-for-byte with a published upstream release.

- `recorded-transport-url.mjs`: the recorded URL parser and query/path helpers from `src/domain/recordedTransportUrl.ts`.
- `route-rule.mjs`: only `segmentRule` from `src/domain/analysisView/webNetworkRouteTemplates.ts`.

`provenance.json` records source-file hashes and the transformation. Runtime expressions were preserved; the project's existing TypeScript compiler removed type annotations. Keep these files, the MIT `LICENSE` and provenance together. No analysis engine, installer, browser controller, native bridge or upstream MCP server is included.

The wrapper in `../../source-evidence.mjs` owns its narrower scope, reporting policy and tests. It does not claim full REA compatibility or coverage.
