"""M1 signal-policy and optimization capability.

Deterministic scoring of intersection approaches from supplied traffic-state
information, plus a signal-green recommendation built from that score. This is
a standalone policy capability for the future AI Decision Engine; it is NOT a
safety-certified traffic-signal controller and never talks to SUMO/TraCI.
"""