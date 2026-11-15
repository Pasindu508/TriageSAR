# Security

TriageSAR is a hackathon research prototype. It has not had a security review.

## Design choices that limit risk

- **The public API is read-only** (GET only) and serves results computed from a prepared fixture. It never
  downloads NASA data and never needs credentials.
- **No request parameter becomes a file path.** Event ids are checked against a strict pattern and then
  looked up in a registry (`data/fixtures/demo_manifest.json`); raster layer names are an allow-list.
- **Credentials stay on the developer machine.** NASA Earthdata credentials are read from the environment,
  a git-ignored `.env`, or `~/.netrc`, are used only by the ingestion scripts, and are never logged, printed,
  written to a fixture, or bundled into the web app or the Docker image.
- **No shell-outs with user input.** Scripts validate bounding boxes, dates, product names and download hosts.
- **Structured request logs** contain method, path, status and duration only: no headers, no bodies.
- The container runs as a non-root user on a read-only file system.

## Reporting a problem

Please open a private security advisory on the project's GitHub repository, or an issue that does not
include exploit details. Do not include real credentials in any report.

## Known gaps

No authentication or rate limiting (the data are public and the API is read-only), and dependency
vulnerability checks in CI are advisory rather than blocking.
