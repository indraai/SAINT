# Model file format

A pySAINT model is one YAML (`.yaml`/`.yml`) or JSON (`.json`) file. YAML is
easier to write by hand; JSON is handy for programs. Both have exactly the same
structure. Working examples are in [`examples/yaml/`](../examples/yaml):

| File | Shows |
|---|---|
| `inspection_network.yaml` | parallel tasks, join (`pr1: 2`), probabilistic rework loop, one resource |
| `two_operator_queue.yaml` | arrivals loop, queue for one of two operators (`OR`), time-in-system statistic |
| `conditional_routing.yaml` | attribute assignment, conditional take-first routing, two resources |

Check any file with `saint validate FILE`.

## Overall shape

```yaml
saint: "1.0"            # format version (optional)
general: {...}          # run settings
options: {...}          # queue ranking rule
distributions: {...}    # numbered random distributions
resources: {...}        # numbered resources
system_attrs: {...}     # numbered global values (SA)
tasks: {...}            # numbered tasks (the network)
```

Collections are **maps from id number to definition**: `tasks: {1: {...}, 2: {...}}`.
(You may also write a list of items that each have an `id:`.) Unknown field names
are rejected, which catches typos.

## `general`

| Field | Default | Meaning |
|---|---|---|
| `name` | `MODEL` | Name shown in reports. |
| `iterations` | `1` | How many independent runs. Can be overridden by `--iterations` / the UI. |
| `sinks_to_complete` | `1` | An iteration ends when this many sink-task completions have happened. `0`: run until nothing is left to do. |
| `seed` | `71268659` | Base random seed. Same seed = same results. |
| `scale` | `1.0` | All `SC` constants are divided by this (SAINT time scaling). |
| `max_time` | infinite | Safety limit: stop an iteration at this simulated time (noted in warnings). |
| `max_events` | `10000000` | Safety limit: error if an iteration needs more events. |

## `options`

| Field | Default | Values |
|---|---|---|
| `ranking` | `FIFO` | How tasks waiting for a resource are ordered: `FIFO`, `LIFO`, `LOW` (lowest `priority` first), `HIGH` (highest first). |

## `distributions`

Numbered distribution sets, referenced from a task as `time: {DS: n}`.

```yaml
distributions:
  1: {type: NO, mean: 4.0, sd: 1.0, min: 1.0, max: 8.0}
  2: {type: EX, mean: 2.0}
```

| `type` (alias) | Parameters | Notes |
|---|---|---|
| `CO` (constant) | `value` | Always the same value. |
| `NO` (normal) | `mean`, `sd` | `min` defaults to 0 so times are never negative. |
| `LO` (lognormal) | `mean`, `sd` | Mean and sd of the result itself. |
| `GA` (gamma) | `mean`, `sd` | |
| `BE` (beta) | `mean`, `sd`, `min`, `max` | On the interval [min, max]. |
| `UN` (uniform) | `min`, `max` | |
| `ER` (Erlang) | `mean`, `k` | Sum of `k` exponentials, each with this mean. |
| `EX` (exponential) | `mean` | pySAINT shortcut for `ER` with `k: 1`. |
| `PO` (Poisson) | `mean` | Result is `min` + Poisson(mean). |
| `TR` (triangular) | `mode`, `min`, `max` | |
| `BP` (beta-PERT) | `mode`, `min`, `max` | |
| `WE` (Weibull) | `alpha` (scale), `shape` | |

`min` / `max` (also written `low` / `high`) **clamp** samples: a value below
`min` becomes `min`. This matches original SAINT (it is not truncation).

## Values (`time`, assignments)

Wherever a number is needed you can write:

| Form | Meaning |
|---|---|
| `3.5` or `{SC: 3.5}` | Constant (divided by `general.scale`). |
| `{DS: 2}` | A sample from distribution set 2. |
| `{dist: {type: EX, mean: 2}}` | An inline distribution. |
| `{IA: 1}` | Information attribute 1 of the packet the task is carrying. |
| `{SA: 1}` | System attribute 1. |
| `{UF: 1}` | User function 1 (Python only: `Simulation(model, userf=...)`). |

## `resources`

```yaml
resources:
  1: {label: OPERATOR}
  2: {label: RADAR, attrs: {1: 0.9}}
```

A resource can serve one task at a time. Utilization (fraction of the iteration it
was busy) is reported for every resource.

## `system_attrs`

Global numbers shared by all tasks, e.g. `system_attrs: {1: 0.0, 2: 10.0}`. Tasks
can read them (`{SA: 1}`), set them (assignments) and test them (conditions).

## `tasks`

```yaml
tasks:
  4:
    label: INSPECT
    pr1: 2
    pr2: 1
    time: {DS: 3}
    resources: {mode: AND, ids: [1]}
    stat: {type: NUM, at: COM}
    branching:
      type: PRO
      branches: [{to: 6, p: 0.8}, {to: 5, p: 0.2}]
```

| Field | Default | Meaning |
|---|---|---|
| `label` | `""` | Name shown in reports and the diagram. |
| `role` | `normal` | `source` (released at time 0), `sink` (completion counts toward ending the iteration) or `normal`. Codes `SO`/`SI`/`NS` also accepted. |
| `pr1` | 0 for sources, else 1 | Predecessor completions needed to release the task the **first** time. |
| `pr2` | `9999` | Completions needed for **each later** release. The default effectively means "only once"; use `pr2: 1` for loops and repeated tasks. |
| `time` | `0` | Task duration (see Values). |
| `priority` | `0` | Ranking value used by `LOW`/`HIGH` ranking. |
| `diff` | `false` | Count only completions from *different* predecessors toward release. |
| `incm` | `LAST` | Which incoming packet the task keeps when several arrive: `FIRST`, `LAST`, `BIG`, `SMALL` (by attribute `incm_attr`). |
| `incm_attr` | - | Attribute compared by `BIG`/`SMALL`. |
| `resources` | none | `{mode: AND, ids: [1, 2]}` needs all; `{mode: OR, ids: [1, 2]}` needs any one. A released task waits in the queue until they are free. |
| `branching` | none | Where to go after completion (below). A task without branching just ends. |
| `stat` | none | Extra statistic(s) to collect; one item or a list (below). |
| `mark` | none | `{at: REL}`: remember the time at this event in the packet (used by `INT` statistics). |
| `assignments` | none | List of `{at, target, index, value}`: set `IA`/`SA` number `index` to `value` at event `at`. |

Event points (`at`): `REL` released, `STA` started, `COM` completed, `FPC` first
predecessor completion (marks only).

### Branching

```yaml
branching: {type: DET, successors: [2, 3]}                 # shorthand
branching: {type: PRO, branches: [{to: 6, p: 0.8}, {to: 5, p: 0.2}]}
```

| `type` | Meaning |
|---|---|
| `DET` deterministic | Signal **every** successor. |
| `PRO` probabilistic | Signal **exactly one**, chosen with probabilities `p` (must sum to 1). |
| `CFI` conditional, take first | Test conditions in order; signal the first true one. |
| `CAL` conditional, take all | Signal every successor whose condition is true. |

Conditional branches each need a `condition`. Use `{code: NO}` ("always true") for
an "otherwise" branch, and put it last in `CFI`.

```yaml
branching:
  type: CFI
  branches:
    - {to: 4, condition: {code: AGV, attr: 1, value: 5.0}}   # IA1 > 5
    - {to: 3, condition: {code: NO}}                         # otherwise
```

| `code` | True when (`x` = `value`, `A` = `attr`, `B` = `attr2`, `N` = `task`) |
|---|---|
| `NO` | always |
| `TLV` / `TGV` | current time <= x / > x |
| `TLA` / `TGA` | current time <= / > attribute A |
| `TVC` / `TVN` | task N has / has not completed |
| `TAC` / `TAN` | task numbered by attribute A has / has not completed |
| `ALV` / `AGV` | attribute A <= x / > x |
| `ALA` / `AGA` | attribute A <= / > attribute B |

`attr_type: IA` (default) reads packet attributes; `attr_type: SA` reads system
attributes.

### Statistics

Every task automatically gets `completion_time`, `duration` (start to finish) and
`interval` (time between completions). Add more with `stat`:

| `type` | Records |
|---|---|
| `FIR` | time of the first event in the iteration |
| `ALL` | time of every event |
| `BET` | time between events |
| `INT` | time since the packet's `mark` (e.g. time in system) |
| `NUM` | number of events per iteration |

`at` picks the event point (default `COM`). They appear in reports as e.g. `INT-COM`.

## Validation messages

| Code | Meaning |
|---|---|
| I201 | Bad distribution parameters |
| I401 | Unknown successor task |
| I402 | Unknown resource |
| I403 | Unknown distribution set |
| I404 | Resource listed twice in one task |
| I405 | Unknown task in a condition |
| I406 | User function used (warning: needs Python `userf`) |
| I501 | `PRO` probabilities do not sum to 1 |
| I502 | Missing or negative probability |
| I503 | No source task |
| I504 | No sink task but `sinks_to_complete` > 0 |
| I505 | `CFI` "always" branch not last |
| I506 | No sink reachable from a source (warning) |
| I507 | Conditional branch without a condition |
| I508 | Branching block with no branches |

Schema errors (wrong field names, wrong types) are reported before these, with
their location, e.g. `tasks.1.bogus: Extra inputs are not permitted`.

## Minimal model

```yaml
general: {name: TINY, iterations: 5}
resources: {1: {label: OP}}
tasks:
  1: {label: A, role: source, time: 2, resources: {ids: [1]}, branching: {successors: [2]}}
  2: {label: B, role: sink, time: 3}
```
