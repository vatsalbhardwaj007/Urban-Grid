"""M1 routing capability (road network, edge costs, route planning).

Standalone AI capability: models a directed road network as a weighted
graph, computes future-looking edge costs, and plans shortest-cost routes.
Independent of SUMO/TraCI; the future AI Decision Engine consumes this API.
"""