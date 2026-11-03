Modern YAML model examples (spec §5.4, App. C). Field reference: ../../docs/model-format.md

- inspection_network.yaml: parallel checks, join, probabilistic rework loop
- two_operator_queue.yaml: M/M/2 queue with OR resources
- conditional_routing.yaml: attribute assignment and conditional take-first routing

Run one: `saint run examples/yaml/inspection_network.yaml -n 100 -s 1`
