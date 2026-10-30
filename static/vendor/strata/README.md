# Strata Web UI attribution and integration

This directory contains the Strata web UI from the user's R7-260 working copy,
read on 2026-10-30 from `serve/web`. The repository describes this checkout as
Strata app 0.2.6. It is a fixed copy, not an automatic update channel.

Copyright (c) 2026 Niko1221 and the Strata contributors. Distributed under the
MIT License; the full notice is in `LICENSE.txt`.

Mini-Server changes are limited to the gateway-relative API base, the local
sprite path, the accurate 260 deployment message, and MCP tools defaulting off
in this embedded UI. Fonts remain served by the existing Strata font endpoint;
Strata's original font files remain on that server. Their notice is also copied
here as `OFL-Outfit.txt`.

The original HTML is adapted into `templates/strata_console.html`, with website
CSRF/storage metadata, fixed local asset links and an explanatory authentication
banner. The API-key input stays structurally present for compatibility but is
hidden. `strata_bridge.js` prevents this UI from storing or sending a shared API
key and supplies website CSRF on writes. Nginx provides the actual upstream key.

Refresh this copy intentionally when the Strata API/UI version changes and rerun
the integration, session, Nginx streaming and browser checks. Do not load changed
upstream JavaScript automatically into the authenticated website origin.
