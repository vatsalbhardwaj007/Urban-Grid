"""M1 AI Decision Engine.

Combines the completed M1 capabilities (prediction, routing, signals) into a
single deterministic decision: does the current congestion forecast warrant an
intervention, and if so, which single action is best? This is decision logic
only — it never talks to SUMO/TraCI, databases, or frontends.
"""