# SAINT

Modern SAINT (Systems Analysis of Integrated Networks of Tasks): `pysaint`, a Python re-implementation of the
combined discrete/continuous man-machine network simulation language developed by Pritsker & Associates
for the USAF Aerospace Medical Research Laboratory (1974-1978).

Status: project layout only. Nothing is implemented yet.

- Build specification: [docs/SAINT_modern_build_spec.md](docs/SAINT_modern_build_spec.md)
- Primary source: *The SAINT User's Manual*, AMRL-TR-77-62, June 1978.

## Layout

See spec section 3.2. Modules: `model`, `legacy` (card-deck parser), `io`, `kernel` (discrete-event engine),
`continuous` (state variables and monitors), `plugins` (user hooks), `stats`, `report`, `ext` (optional phase 2).

## Roadmap

P0 foundations, P1 legacy input, P2 discrete kernel, P3 continuous, P4 plugins/stats/reports, P5 hardening
(v1.0), P6 optional extras. Details in spec section 13.1.
