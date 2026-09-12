#!/usr/bin/env python3
"""Build and generate all SUMO simulation MVP files for Urban Grid.

Produces:
- network.net.xml (SUMO complete network file)
- nodes.nod.xml, edges.edg.xml, connections.con.xml (SUMO plain XML definitions)
- routes.rou.xml (Full sequential scenarios: Normal -> Congestion -> Intervention-ready)
- routes_normal.rou.xml (Standalone Scenario A)
- routes_congested.rou.xml (Standalone Scenario B)
- routes_intervention_ready.rou.xml (Standalone Scenario C)
- traffic_lights.add.xml (Fixed-time signal programs)
- urban_grid.sumocfg (Main SUMO configuration)
- viewsettings.xml (GUI visualization settings)
"""

import os
from pathlib import Path

SUMO_DIR = Path(__file__).resolve().parent


def build_nodes_nod_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    <!-- 4 Signalized Main Intersections -->
    <node id="I1" x="250.0" y="750.0" type="traffic_light"/>
    <node id="I2" x="750.0" y="750.0" type="traffic_light"/>
    <node id="I3" x="250.0" y="250.0" type="traffic_light"/>
    <node id="I4" x="750.0" y="250.0" type="traffic_light"/>

    <!-- External Entry / Exit Approach Nodes -->
    <node id="J_W1" x="0.0" y="750.0" type="priority"/>
    <node id="J_E2" x="1000.0" y="750.0" type="priority"/>
    <node id="J_W3" x="0.0" y="250.0" type="priority"/>
    <node id="J_E4" x="1000.0" y="250.0" type="priority"/>
    <node id="J_N1" x="250.0" y="1000.0" type="priority"/>
    <node id="J_N2" x="750.0" y="1000.0" type="priority"/>
    <node id="J_S3" x="250.0" y="0.0" type="priority"/>
    <node id="J_S4" x="750.0" y="0.0" type="priority"/>
</nodes>
"""


def build_edges_edg_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    <!-- Internal Horizontal Edges (2 lanes, 50 km/h = 13.89 m/s) -->
    <edge id="E_I1_I2" from="I1" to="I2" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I2_I1" from="I2" to="I1" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I3_I4" from="I3" to="I4" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I4_I3" from="I4" to="I3" priority="2" numLanes="2" speed="13.89"/>

    <!-- Internal Vertical Edges (2 lanes, 50 km/h = 13.89 m/s) -->
    <edge id="E_I1_I3" from="I1" to="I3" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I3_I1" from="I3" to="I1" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I2_I4" from="I2" to="I4" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I4_I2" from="I4" to="I2" priority="2" numLanes="2" speed="13.89"/>

    <!-- External Approaches to/from I1 -->
    <edge id="E_W1_I1" from="J_W1" to="I1" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I1_W1" from="I1" to="J_W1" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_N1_I1" from="J_N1" to="I1" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I1_N1" from="I1" to="J_N1" priority="2" numLanes="2" speed="13.89"/>

    <!-- External Approaches to/from I2 -->
    <edge id="E_N2_I2" from="J_N2" to="I2" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I2_N2" from="I2" to="J_N2" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I2_E2" from="I2" to="J_E2" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_E2_I2" from="J_E2" to="I2" priority="2" numLanes="2" speed="13.89"/>

    <!-- External Approaches to/from I3 -->
    <edge id="E_W3_I3" from="J_W3" to="I3" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I3_W3" from="I3" to="J_W3" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_S3_I3" from="J_S3" to="I3" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I3_S3" from="I3" to="J_S3" priority="2" numLanes="2" speed="13.89"/>

    <!-- External Approaches to/from I4 -->
    <edge id="E_S4_I4" from="J_S4" to="I4" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I4_S4" from="I4" to="J_S4" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_I4_E4" from="I4" to="J_E4" priority="2" numLanes="2" speed="13.89"/>
    <edge id="E_E4_I4" from="J_E4" to="I4" priority="2" numLanes="2" speed="13.89"/>
</edges>
"""


def build_connections_con_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<connections xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/connections_file.xsd">
    <!-- Connections at I1 -->
    <!-- From North E_N1_I1 -->
    <connection from="E_N1_I1" to="E_I1_W1" fromLane="0" toLane="0"/>
    <connection from="E_N1_I1" to="E_I1_I3" fromLane="0" toLane="0"/>
    <connection from="E_N1_I1" to="E_I1_I3" fromLane="1" toLane="1"/>
    <connection from="E_N1_I1" to="E_I1_I2" fromLane="1" toLane="1"/>
    <!-- From East E_I2_I1 -->
    <connection from="E_I2_I1" to="E_I1_N1" fromLane="0" toLane="0"/>
    <connection from="E_I2_I1" to="E_I1_W1" fromLane="0" toLane="0"/>
    <connection from="E_I2_I1" to="E_I1_W1" fromLane="1" toLane="1"/>
    <connection from="E_I2_I1" to="E_I1_I3" fromLane="1" toLane="1"/>
    <!-- From South E_I3_I1 -->
    <connection from="E_I3_I1" to="E_I1_I2" fromLane="0" toLane="0"/>
    <connection from="E_I3_I1" to="E_I1_N1" fromLane="0" toLane="0"/>
    <connection from="E_I3_I1" to="E_I1_N1" fromLane="1" toLane="1"/>
    <connection from="E_I3_I1" to="E_I1_W1" fromLane="1" toLane="1"/>
    <!-- From West E_W1_I1 -->
    <connection from="E_W1_I1" to="E_I1_I3" fromLane="0" toLane="0"/>
    <connection from="E_W1_I1" to="E_I1_I2" fromLane="0" toLane="0"/>
    <connection from="E_W1_I1" to="E_I1_I2" fromLane="1" toLane="1"/>
    <connection from="E_W1_I1" to="E_I1_N1" fromLane="1" toLane="1"/>

    <!-- Connections at I2 -->
    <!-- From North E_N2_I2 -->
    <connection from="E_N2_I2" to="E_I2_I1" fromLane="0" toLane="0"/>
    <connection from="E_N2_I2" to="E_I2_I4" fromLane="0" toLane="0"/>
    <connection from="E_N2_I2" to="E_I2_I4" fromLane="1" toLane="1"/>
    <connection from="E_N2_I2" to="E_I2_E2" fromLane="1" toLane="1"/>
    <!-- From East E_E2_I2 -->
    <connection from="E_E2_I2" to="E_I2_N2" fromLane="0" toLane="0"/>
    <connection from="E_E2_I2" to="E_I2_I1" fromLane="0" toLane="0"/>
    <connection from="E_E2_I2" to="E_I2_I1" fromLane="1" toLane="1"/>
    <connection from="E_E2_I2" to="E_I2_I4" fromLane="1" toLane="1"/>
    <!-- From South E_I4_I2 -->
    <connection from="E_I4_I2" to="E_I2_E2" fromLane="0" toLane="0"/>
    <connection from="E_I4_I2" to="E_I2_N2" fromLane="0" toLane="0"/>
    <connection from="E_I4_I2" to="E_I2_N2" fromLane="1" toLane="1"/>
    <connection from="E_I4_I2" to="E_I2_I1" fromLane="1" toLane="1"/>
    <!-- From West E_I1_I2 -->
    <connection from="E_I1_I2" to="E_I2_I4" fromLane="0" toLane="0"/>
    <connection from="E_I1_I2" to="E_I2_E2" fromLane="0" toLane="0"/>
    <connection from="E_I1_I2" to="E_I2_E2" fromLane="1" toLane="1"/>
    <connection from="E_I1_I2" to="E_I2_N2" fromLane="1" toLane="1"/>

    <!-- Connections at I3 -->
    <!-- From North E_I1_I3 -->
    <connection from="E_I1_I3" to="E_I3_W3" fromLane="0" toLane="0"/>
    <connection from="E_I1_I3" to="E_I3_S3" fromLane="0" toLane="0"/>
    <connection from="E_I1_I3" to="E_I3_S3" fromLane="1" toLane="1"/>
    <connection from="E_I1_I3" to="E_I3_I4" fromLane="1" toLane="1"/>
    <!-- From East E_I4_I3 -->
    <connection from="E_I4_I3" to="E_I3_I1" fromLane="0" toLane="0"/>
    <connection from="E_I4_I3" to="E_I3_W3" fromLane="0" toLane="0"/>
    <connection from="E_I4_I3" to="E_I3_W3" fromLane="1" toLane="1"/>
    <connection from="E_I4_I3" to="E_I3_S3" fromLane="1" toLane="1"/>
    <!-- From South E_S3_I3 -->
    <connection from="E_S3_I3" to="E_I3_I4" fromLane="0" toLane="0"/>
    <connection from="E_S3_I3" to="E_I3_I1" fromLane="0" toLane="0"/>
    <connection from="E_S3_I3" to="E_I3_I1" fromLane="1" toLane="1"/>
    <connection from="E_S3_I3" to="E_I3_W3" fromLane="1" toLane="1"/>
    <!-- From West E_W3_I3 -->
    <connection from="E_W3_I3" to="E_I3_S3" fromLane="0" toLane="0"/>
    <connection from="E_W3_I3" to="E_I3_I4" fromLane="0" toLane="0"/>
    <connection from="E_W3_I3" to="E_I3_I4" fromLane="1" toLane="1"/>
    <connection from="E_W3_I3" to="E_I3_I1" fromLane="1" toLane="1"/>

    <!-- Connections at I4 -->
    <!-- From North E_I2_I4 -->
    <connection from="E_I2_I4" to="E_I4_I3" fromLane="0" toLane="0"/>
    <connection from="E_I2_I4" to="E_I4_S4" fromLane="0" toLane="0"/>
    <connection from="E_I2_I4" to="E_I4_S4" fromLane="1" toLane="1"/>
    <connection from="E_I2_I4" to="E_I4_E4" fromLane="1" toLane="1"/>
    <!-- From East E_E4_I4 -->
    <connection from="E_E4_I4" to="E_I4_I2" fromLane="0" toLane="0"/>
    <connection from="E_E4_I4" to="E_I4_I3" fromLane="0" toLane="0"/>
    <connection from="E_E4_I4" to="E_I4_I3" fromLane="1" toLane="1"/>
    <connection from="E_E4_I4" to="E_I4_S4" fromLane="1" toLane="1"/>
    <!-- From South E_S4_I4 -->
    <connection from="E_S4_I4" to="E_I4_E4" fromLane="0" toLane="0"/>
    <connection from="E_S4_I4" to="E_I4_I2" fromLane="0" toLane="0"/>
    <connection from="E_S4_I4" to="E_I4_I2" fromLane="1" toLane="1"/>
    <connection from="E_S4_I4" to="E_I4_I3" fromLane="1" toLane="1"/>
    <!-- From West E_I3_I4 -->
    <connection from="E_I3_I4" to="E_I4_S4" fromLane="0" toLane="0"/>
    <connection from="E_I3_I4" to="E_I4_E4" fromLane="0" toLane="0"/>
    <connection from="E_I3_I4" to="E_I4_E4" fromLane="1" toLane="1"/>
    <connection from="E_I3_I4" to="E_I4_I2" fromLane="1" toLane="1"/>
</connections>
"""


def build_network_net_xml() -> str:
    """Construct complete valid SUMO network XML file."""
    # Build complete network XML with edges, lanes, junctions, connections, and tlLogic
    xml_parts = [
        """<?xml version="1.0" encoding="UTF-8"?>
<net version="1.20" junctionCornerDetail="5" limitTurnSpeed="5.50" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">
    <location netOffset="0.00,0.00" convBoundary="0.00,0.00,1000.00,1000.00" origBoundary="0.00,0.00,1000.00,1000.00" projParameter="!"/>
"""
    ]

    # Define edges and lanes
    # Geometry helper
    edges_def = [
        # id, from, to, len, l0_shape, l1_shape
        ("E_W1_I1", "J_W1", "I1", 250.0, "0.00,745.20 250.00,745.20", "0.00,748.40 250.00,748.40"),
        ("E_I1_W1", "I1", "J_W1", 250.0, "250.00,754.80 0.00,754.80", "250.00,751.60 0.00,751.60"),
        ("E_I1_I2", "I1", "I2", 500.0, "250.00,745.20 750.00,745.20", "250.00,748.40 750.00,748.40"),
        ("E_I2_I1", "I2", "I1", 500.0, "750.00,754.80 250.00,754.80", "750.00,751.60 250.00,751.60"),
        ("E_I2_E2", "I2", "J_E2", 250.0, "750.00,745.20 1000.00,745.20", "750.00,748.40 1000.00,748.40"),
        ("E_E2_I2", "J_E2", "I2", 250.0, "1000.00,754.80 750.00,754.80", "1000.00,751.60 750.00,751.60"),

        ("E_W3_I3", "J_W3", "I3", 250.0, "0.00,245.20 250.00,245.20", "0.00,248.40 250.00,248.40"),
        ("E_I3_W3", "I3", "J_W3", 250.0, "250.00,254.80 0.00,254.80", "250.00,251.60 0.00,251.60"),
        ("E_I3_I4", "I3", "I4", 500.0, "250.00,245.20 750.00,245.20", "250.00,248.40 750.00,248.40"),
        ("E_I4_I3", "I4", "I3", 500.0, "750.00,254.80 250.00,254.80", "750.00,251.60 250.00,251.60"),
        ("E_I4_E4", "I4", "J_E4", 250.0, "750.00,245.20 1000.00,245.20", "750.00,248.40 1000.00,248.40"),
        ("E_E4_I4", "J_E4", "I4", 250.0, "1000.00,254.80 750.00,254.80", "1000.00,251.60 750.00,251.60"),

        ("E_N1_I1", "J_N1", "I1", 250.0, "245.20,1000.00 245.20,750.00", "248.40,1000.00 248.40,750.00"),
        ("E_I1_N1", "I1", "J_N1", 250.0, "254.80,750.00 254.80,1000.00", "251.60,750.00 251.60,1000.00"),
        ("E_I1_I3", "I1", "I3", 500.0, "245.20,750.00 245.20,250.00", "248.40,750.00 248.40,250.00"),
        ("E_I3_I1", "I3", "I1", 500.0, "254.80,250.00 254.80,750.00", "251.60,250.00 251.60,750.00"),
        ("E_I3_S3", "I3", "J_S3", 250.0, "245.20,250.00 245.20,0.00", "248.40,250.00 248.40,0.00"),
        ("E_S3_I3", "J_S3", "I3", 250.0, "254.80,0.00 254.80,250.00", "251.60,0.00 251.60,250.00"),

        ("E_N2_I2", "J_N2", "I2", 250.0, "745.20,1000.00 745.20,750.00", "748.40,1000.00 748.40,750.00"),
        ("E_I2_N2", "I2", "J_N2", 250.0, "754.80,750.00 754.80,1000.00", "751.60,750.00 751.60,1000.00"),
        ("E_I2_I4", "I2", "I4", 500.0, "745.20,750.00 745.20,250.00", "748.40,750.00 748.40,250.00"),
        ("E_I4_I2", "I4", "I2", 500.0, "754.80,250.00 754.80,750.00", "751.60,250.00 751.60,750.00"),
        ("E_I4_S4", "I4", "J_S4", 250.0, "745.20,250.00 745.20,0.00", "748.40,250.00 748.40,0.00"),
        ("E_S4_I4", "J_S4", "I4", 250.0, "754.80,0.00 754.80,250.00", "751.60,0.00 751.60,250.00"),
    ]

    for eid, fr, to, length, l0, l1 in edges_def:
        xml_parts.append(
            f'    <edge id="{eid}" from="{fr}" to="{to}" priority="2">\n'
            f'        <lane id="{eid}_0" index="0" speed="13.89" length="{length:.2f}" shape="{l0}"/>\n'
            f'        <lane id="{eid}_1" index="1" speed="13.89" length="{length:.2f}" shape="{l1}"/>\n'
            f'    </edge>\n'
        )

    # Traffic light logics in net
    for tl_id in ["I1", "I2", "I3", "I4"]:
        xml_parts.append(
            f'    <tlLogic id="{tl_id}" type="static" programID="0" offset="0">\n'
            f'        <phase duration="31" state="GGGGrrrrGGGGrrrr" name="NS_GREEN"/>\n'
            f'        <phase duration="4"  state="yyyyrrrryyyyrrrr" name="NS_YELLOW"/>\n'
            f'        <phase duration="31" state="rrrrGGGGrrrrGGGG" name="EW_GREEN"/>\n'
            f'        <phase duration="4"  state="rrrryyyyrrrryyyy" name="EW_YELLOW"/>\n'
            f'    </tlLogic>\n'
        )

    # Junctions
    # 4 Main signalized junctions
    signalized_juncs = [
        ("I1", 250.0, 750.0, "E_N1_I1_0 E_N1_I1_1 E_I2_I1_0 E_I2_I1_1 E_I3_I1_0 E_I3_I1_1 E_W1_I1_0 E_W1_I1_1"),
        ("I2", 750.0, 750.0, "E_N2_I2_0 E_N2_I2_1 E_E2_I2_0 E_E2_I2_1 E_I4_I2_0 E_I4_I2_1 E_I1_I2_0 E_I1_I2_1"),
        ("I3", 250.0, 250.0, "E_I1_I3_0 E_I1_I3_1 E_I4_I3_0 E_I4_I3_1 E_S3_I3_0 E_S3_I3_1 E_W3_I3_0 E_W3_I3_1"),
        ("I4", 750.0, 250.0, "E_I2_I4_0 E_I2_I4_1 E_E4_I4_0 E_E4_I4_1 E_S4_I4_0 E_S4_I4_1 E_I3_I4_0 E_I3_I4_1"),
    ]
    for jid, jx, jy, inc_lanes in signalized_juncs:
        shape = f"{jx-8.0:.2f},{jy+8.0:.2f} {jx+8.0:.2f},{jy+8.0:.2f} {jx+8.0:.2f},{jy-8.0:.2f} {jx-8.0:.2f},{jy-8.0:.2f}"
        xml_parts.append(
            f'    <junction id="{jid}" type="traffic_light" x="{jx:.2f}" y="{jy:.2f}" incLanes="{inc_lanes}" shape="{shape}"/>\n'
        )

    # Boundary priority junctions
    boundary_juncs = [
        ("J_W1", 0.0, 750.0, "E_I1_W1_0 E_I1_W1_1"),
        ("J_E2", 1000.0, 750.0, "E_I2_E2_0 E_I2_E2_1"),
        ("J_W3", 0.0, 250.0, "E_I3_W3_0 E_I3_W3_1"),
        ("J_E4", 1000.0, 250.0, "E_I4_E4_0 E_I4_E4_1"),
        ("J_N1", 250.0, 1000.0, "E_I1_N1_0 E_I1_N1_1"),
        ("J_N2", 750.0, 1000.0, "E_I2_N2_0 E_I2_N2_1"),
        ("J_S3", 250.0, 0.0, "E_I3_S3_0 E_I3_S3_1"),
        ("J_S4", 750.0, 0.0, "E_I4_S4_0 E_I4_S4_1"),
    ]
    for jid, jx, jy, inc_lanes in boundary_juncs:
        xml_parts.append(
            f'    <junction id="{jid}" type="priority" x="{jx:.2f}" y="{jy:.2f}" incLanes="{inc_lanes}"/>\n'
        )

    # Connections with traffic light link indices (16 links per intersection)
    # Helper to generate standard 4-way connections for an intersection
    def intersection_connections(tl_id, north_in, east_in, south_in, west_in, north_out, east_out, south_out, west_out):
        conns = []
        # North approach (links 0..3)
        conns.append((north_in, west_out, 0, 0, "r", 0))
        conns.append((north_in, south_out, 0, 0, "s", 1))
        conns.append((north_in, south_out, 1, 1, "s", 2))
        conns.append((north_in, east_out, 1, 1, "l", 3))
        # East approach (links 4..7)
        conns.append((east_in, north_out, 0, 0, "r", 4))
        conns.append((east_in, west_out, 0, 0, "s", 5))
        conns.append((east_in, west_out, 1, 1, "s", 6))
        conns.append((east_in, south_out, 1, 1, "l", 7))
        # South approach (links 8..11)
        conns.append((south_in, east_out, 0, 0, "r", 8))
        conns.append((south_in, north_out, 0, 0, "s", 9))
        conns.append((south_in, north_out, 1, 1, "s", 10))
        conns.append((south_in, west_out, 1, 1, "l", 11))
        # West approach (links 12..15)
        conns.append((west_in, south_out, 0, 0, "r", 12))
        conns.append((west_in, east_out, 0, 0, "s", 13))
        conns.append((west_in, east_out, 1, 1, "s", 14))
        conns.append((west_in, north_out, 1, 1, "l", 15))

        lines = []
        for fr, to, fr_l, to_l, d, idx in conns:
            lines.append(
                f'    <connection from="{fr}" to="{to}" fromLane="{fr_l}" toLane="{to_l}" tl="{tl_id}" linkIndex="{idx}" dir="{d}" state="o"/>'
            )
        return "\n".join(lines)

    # I1 connections
    xml_parts.append(intersection_connections("I1", "E_N1_I1", "E_I2_I1", "E_I3_I1", "E_W1_I1", "E_I1_N1", "E_I1_I2", "E_I1_I3", "E_I1_W1"))
    xml_parts.append("\n")
    # I2 connections
    xml_parts.append(intersection_connections("I2", "E_N2_I2", "E_E2_I2", "E_I4_I2", "E_I1_I2", "E_I2_N2", "E_I2_E2", "E_I2_I4", "E_I2_I1"))
    xml_parts.append("\n")
    # I3 connections
    xml_parts.append(intersection_connections("I3", "E_I1_I3", "E_I4_I3", "E_S3_I3", "E_W3_I3", "E_I3_I1", "E_I3_I4", "E_I3_S3", "E_I3_W3"))
    xml_parts.append("\n")
    # I4 connections
    xml_parts.append(intersection_connections("I4", "E_I2_I4", "E_E4_I4", "E_S4_I4", "E_I3_I4", "E_I4_I2", "E_I4_E4", "E_I4_S4", "E_I4_I3"))
    xml_parts.append("\n")

    xml_parts.append("</net>\n")
    return "".join(xml_parts)


def build_traffic_lights_add_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<additional xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/additional_file.xsd">
    <!-- Deterministic fixed-time signal programs for the 4 intersections -->
    <!-- Link indexing per intersection (16 links total):
         Links 0..3:   North approach (r, s, s, l)
         Links 4..7:   East approach  (r, s, s, l)
         Links 8..11:  South approach (r, s, s, l)
         Links 12..15: West approach  (r, s, s, l)
    -->

    <!-- Intersection I1 (Northwest) -->
    <tlLogic id="I1" type="static" programID="0" offset="0">
        <phase duration="31" state="GGGGrrrrGGGGrrrr" name="NS_GREEN"/>
        <phase duration="4"  state="yyyyrrrryyyyrrrr" name="NS_YELLOW"/>
        <phase duration="31" state="rrrrGGGGrrrrGGGG" name="EW_GREEN"/>
        <phase duration="4"  state="rrrryyyyrrrryyyy" name="EW_YELLOW"/>
    </tlLogic>

    <!-- Intersection I2 (Northeast - Bottleneck hotspot in Scenario B) -->
    <tlLogic id="I2" type="static" programID="0" offset="0">
        <phase duration="31" state="GGGGrrrrGGGGrrrr" name="NS_GREEN"/>
        <phase duration="4"  state="yyyyrrrryyyyrrrr" name="NS_YELLOW"/>
        <phase duration="31" state="rrrrGGGGrrrrGGGG" name="EW_GREEN"/>
        <phase duration="4"  state="rrrryyyyrrrryyyy" name="EW_YELLOW"/>
    </tlLogic>

    <!-- Intersection I3 (Southwest - Alternate corridor route) -->
    <tlLogic id="I3" type="static" programID="0" offset="0">
        <phase duration="31" state="GGGGrrrrGGGGrrrr" name="NS_GREEN"/>
        <phase duration="4"  state="yyyyrrrryyyyrrrr" name="NS_YELLOW"/>
        <phase duration="31" state="rrrrGGGGrrrrGGGG" name="EW_GREEN"/>
        <phase duration="4"  state="rrrryyyyrrrryyyy" name="EW_YELLOW"/>
    </tlLogic>

    <!-- Intersection I4 (Southeast) -->
    <tlLogic id="I4" type="static" programID="0" offset="0">
        <phase duration="31" state="GGGGrrrrGGGGrrrr" name="NS_GREEN"/>
        <phase duration="4"  state="yyyyrrrryyyyrrrr" name="NS_YELLOW"/>
        <phase duration="31" state="rrrrGGGGrrrrGGGG" name="EW_GREEN"/>
        <phase duration="4"  state="rrrryyyyrrrryyyy" name="EW_YELLOW"/>
    </tlLogic>
</additional>
"""


def build_routes_common_header() -> str:
    return """    <!-- Vehicle Types (sigma=0.0 ensures 100% deterministic simulation) -->
    <vType id="standard_car" accel="2.6" decel="4.5" sigma="0.0" length="5.0" minGap="2.5" maxSpeed="13.89" color="0.2,0.6,1.0"/>
    <vType id="congested_car" accel="2.6" decel="4.5" sigma="0.0" length="5.0" minGap="2.5" maxSpeed="13.89" color="1.0,0.25,0.25"/>
    <vType id="alternate_car" accel="2.6" decel="4.5" sigma="0.0" length="5.0" minGap="2.5" maxSpeed="13.89" color="0.25,0.9,0.3"/>

    <!-- Key Routing Corridors -->
    <!-- PRIMARY: via I1 -> I2 -> I4 -->
    <route id="route_primary" edges="E_W1_I1 E_I1_I2 E_I2_I4 E_I4_E4"/>

    <!-- ALTERNATE: via I1 -> I3 -> I4 (For load redistribution) -->
    <route id="route_alternate" edges="E_W1_I1 E_I1_I3 E_I3_I4 E_I4_E4"/>

    <!-- Cross-Traffic & Network Feeding Routes -->
    <route id="route_N2_I2_S4" edges="E_N2_I2 E_I2_I4 E_I4_S4"/>
    <route id="route_E2_I2_W1" edges="E_E2_I2 E_I2_I1 E_I1_W1"/>
    <route id="route_N1_I1_S3" edges="E_N1_I1 E_I1_I3 E_I3_S3"/>
    <route id="route_W3_I3_E4" edges="E_W3_I3 E_I3_I4 E_I4_E4"/>
    <route id="route_S3_I3_N1" edges="E_S3_I3 E_I3_I1 E_I1_N1"/>
    <route id="route_S4_I4_N2" edges="E_S4_I4 E_I4_I2 E_I2_N2"/>
"""


def build_routes_rou_xml() -> str:
    """Build the master sequenced route file with Scenario A, B, and C."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
{build_routes_common_header()}
    <!-- =================================================================== -->
    <!-- SCENARIO A: NORMAL TRAFFIC DEMAND (0s to 300s)                      -->
    <!-- Moderate, well-distributed flow across all intersections.            -->
    <!-- Queues clear reliably every cycle; free-flow speeds prevail.       -->
    <!-- =================================================================== -->
    <flow id="flow_norm_prim" route="route_primary" type="standard_car" begin="0" end="300" period="12.0"/>
    <flow id="flow_norm_alt" route="route_alternate" type="standard_car" begin="0" end="300" period="20.0"/>
    <flow id="flow_norm_n2_s4" route="route_N2_I2_S4" type="standard_car" begin="0" end="300" period="15.0"/>
    <flow id="flow_norm_e2_w1" route="route_E2_I2_W1" type="standard_car" begin="0" end="300" period="18.0"/>
    <flow id="flow_norm_n1_s3" route="route_N1_I1_S3" type="standard_car" begin="0" end="300" period="16.0"/>
    <flow id="flow_norm_w3_e4" route="route_W3_I3_E4" type="standard_car" begin="0" end="300" period="18.0"/>
    <flow id="flow_norm_s3_n1" route="route_S3_I3_N1" type="standard_car" begin="0" end="300" period="20.0"/>
    <flow id="flow_norm_s4_n2" route="route_S4_I4_N2" type="standard_car" begin="0" end="300" period="20.0"/>

    <!-- =================================================================== -->
    <!-- SCENARIO B: CONGESTION HOTSPOT AT I2 (300s to 900s)                 -->
    <!-- Heavy surge concentrated toward I2 from West, North, and East.       -->
    <!-- Inflow severely exceeds I2 discharge capacity during green splits.  -->
    <!-- Results in:                                                         -->
    <!-- - Spilling queues on E_I1_I2 and E_N2_I2                            -->
    <!-- - Rising vehicle count and density                                  -->
    <!-- - Mean speed collapsing toward 0 m/s at I2                          -->
    <!-- - Alternate corridor (via I3) remains free-flowing                  -->
    <!-- =================================================================== -->
    <!-- Surging upper corridor traffic into I2 (every 3.0s = 1200 veh/hr) -->
    <flow id="flow_cong_prim" route="route_primary" type="congested_car" begin="300" end="900" period="3.0"/>
    <!-- Surging North approach traffic into I2 (every 4.0s = 900 veh/hr) -->
    <flow id="flow_cong_n2_s4" route="route_N2_I2_S4" type="congested_car" begin="300" end="900" period="4.0"/>
    <!-- Surging East approach traffic into I2 (every 5.0s = 720 veh/hr) -->
    <flow id="flow_cong_e2_w1" route="route_E2_I2_W1" type="congested_car" begin="300" end="900" period="5.0"/>
    <!-- Alternate route kept deliberately light to preserve capacity for intervention -->
    <flow id="flow_cong_alt" route="route_alternate" type="standard_car" begin="300" end="900" period="25.0"/>
    <!-- Moderate background traffic on remaining network legs -->
    <flow id="flow_cong_n1_s3" route="route_N1_I1_S3" type="standard_car" begin="300" end="900" period="16.0"/>
    <flow id="flow_cong_w3_e4" route="route_W3_I3_E4" type="standard_car" begin="300" end="900" period="20.0"/>
    <flow id="flow_cong_s3_n1" route="route_S3_I3_N1" type="standard_car" begin="300" end="900" period="22.0"/>
    <flow id="flow_cong_s4_n2" route="route_S4_I4_N2" type="standard_car" begin="300" end="900" period="22.0"/>

    <!-- =================================================================== -->
    <!-- SCENARIO C: INTERVENTION-READY DEMAND (900s to 1500s)               -->
    <!-- Identical heavy arrival demand as Scenario B.                       -->
    <!-- Fully primed for downstream AI intervention:                         -->
    <!-- 1. Route redistribution: Diverting westbound traffic to alternate   -->
    <!-- 2. Signal timing intervention: Extending I2 green phases            -->
    <!-- (No AI logic is executed here; this sets the canonical benchmark)   -->
    <!-- =================================================================== -->
    <flow id="flow_interv_prim" route="route_primary" type="congested_car" begin="900" end="1500" period="3.0"/>
    <flow id="flow_interv_n2_s4" route="route_N2_I2_S4" type="congested_car" begin="900" end="1500" period="4.0"/>
    <flow id="flow_interv_e2_w1" route="route_E2_I2_W1" type="congested_car" begin="900" end="1500" period="5.0"/>
    <flow id="flow_interv_alt" route="route_alternate" type="alternate_car" begin="900" end="1500" period="25.0"/>
    <flow id="flow_interv_n1_s3" route="route_N1_I1_S3" type="standard_car" begin="900" end="1500" period="16.0"/>
    <flow id="flow_interv_w3_e4" route="route_W3_I3_E4" type="standard_car" begin="900" end="1500" period="20.0"/>
    <flow id="flow_interv_s3_n1" route="route_S3_I3_N1" type="standard_car" begin="900" end="1500" period="22.0"/>
    <flow id="flow_interv_s4_n2" route="route_S4_I4_N2" type="standard_car" begin="900" end="1500" period="22.0"/>
</routes>
"""


def build_routes_scenario_xml(scenario: str) -> str:
    """Build standalone route files for isolated scenario execution."""
    if scenario == "normal":
        flows = """
    <!-- Standalone Scenario A: Normal Traffic (0s - 600s) -->
    <flow id="flow_norm_prim" route="route_primary" type="standard_car" begin="0" end="600" period="12.0"/>
    <flow id="flow_norm_alt" route="route_alternate" type="standard_car" begin="0" end="600" period="20.0"/>
    <flow id="flow_norm_n2_s4" route="route_N2_I2_S4" type="standard_car" begin="0" end="600" period="15.0"/>
    <flow id="flow_norm_e2_w1" route="route_E2_I2_W1" type="standard_car" begin="0" end="600" period="18.0"/>
    <flow id="flow_norm_n1_s3" route="route_N1_I1_S3" type="standard_car" begin="0" end="600" period="16.0"/>
    <flow id="flow_norm_w3_e4" route="route_W3_I3_E4" type="standard_car" begin="0" end="600" period="18.0"/>
    <flow id="flow_norm_s3_n1" route="route_S3_I3_N1" type="standard_car" begin="0" end="600" period="20.0"/>
    <flow id="flow_norm_s4_n2" route="route_S4_I4_N2" type="standard_car" begin="0" end="600" period="20.0"/>
"""
    elif scenario == "congested":
        flows = """
    <!-- Standalone Scenario B: Congestion Hotspot at I2 (0s - 600s) -->
    <flow id="flow_cong_prim" route="route_primary" type="congested_car" begin="0" end="600" period="3.0"/>
    <flow id="flow_cong_n2_s4" route="route_N2_I2_S4" type="congested_car" begin="0" end="600" period="4.0"/>
    <flow id="flow_cong_e2_w1" route="route_E2_I2_W1" type="congested_car" begin="0" end="600" period="5.0"/>
    <flow id="flow_cong_alt" route="route_alternate" type="standard_car" begin="0" end="600" period="25.0"/>
    <flow id="flow_cong_n1_s3" route="route_N1_I1_S3" type="standard_car" begin="0" end="600" period="16.0"/>
    <flow id="flow_cong_w3_e4" route="route_W3_I3_E4" type="standard_car" begin="0" end="600" period="20.0"/>
    <flow id="flow_cong_s3_n1" route="route_S3_I3_N1" type="standard_car" begin="0" end="600" period="22.0"/>
    <flow id="flow_cong_s4_n2" route="route_S4_I4_N2" type="standard_car" begin="0" end="600" period="22.0"/>
"""
    else:  # intervention_ready
        flows = """
    <!-- Standalone Scenario C: Intervention-Ready Conditions (0s - 600s) -->
    <flow id="flow_interv_prim" route="route_primary" type="congested_car" begin="0" end="600" period="3.0"/>
    <flow id="flow_interv_n2_s4" route="route_N2_I2_S4" type="congested_car" begin="0" end="600" period="4.0"/>
    <flow id="flow_interv_e2_w1" route="route_E2_I2_W1" type="congested_car" begin="0" end="600" period="5.0"/>
    <flow id="flow_interv_alt" route="route_alternate" type="alternate_car" begin="0" end="600" period="25.0"/>
    <flow id="flow_interv_n1_s3" route="route_N1_I1_S3" type="standard_car" begin="0" end="600" period="16.0"/>
    <flow id="flow_interv_w3_e4" route="route_W3_I3_E4" type="standard_car" begin="0" end="600" period="20.0"/>
    <flow id="flow_interv_s3_n1" route="route_S3_I3_N1" type="standard_car" begin="0" end="600" period="22.0"/>
    <flow id="flow_interv_s4_n2" route="route_S4_I4_N2" type="standard_car" begin="0" end="600" period="22.0"/>
"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
{build_routes_common_header()}
{flows}
</routes>
"""


def build_urban_grid_sumocfg() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="network.net.xml"/>
        <route-files value="routes.rou.xml"/>
        <additional-files value="traffic_lights.add.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="1500"/>
        <step-length value="1.0"/>
    </time>
    <processing>
        <!-- Preserve queues: do not teleport stuck/queued vehicles -->
        <time-to-teleport value="-1"/>
    </processing>
    <report>
        <verbose value="true"/>
        <no-step-log value="false"/>
        <duration-log.statistics value="true"/>
    </report>
    <gui_only>
        <gui-settings-file value="viewsettings.xml"/>
    </gui_only>
</configuration>
"""


def build_viewsettings_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<viewsettings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/viewsettings_file.xsd">
    <viewport zoom="120" x="500.00" y="500.00"/>
    <scheme name="standard">
        <edges colorScheme="uniform" laneEdgeColor="1" laneShowBorders="1"/>
        <vehicles colorScheme="given vehicle color" vehicleSize="1"/>
        <junctions showLane2Lane="1"/>
    </scheme>
</viewsettings>
"""


def main():
    files = {
        "nodes.nod.xml": build_nodes_nod_xml(),
        "edges.edg.xml": build_edges_edg_xml(),
        "connections.con.xml": build_connections_con_xml(),
        "network.net.xml": build_network_net_xml(),
        "traffic_lights.add.xml": build_traffic_lights_add_xml(),
        "routes.rou.xml": build_routes_rou_xml(),
        "routes_normal.rou.xml": build_routes_scenario_xml("normal"),
        "routes_congested.rou.xml": build_routes_scenario_xml("congested"),
        "routes_intervention_ready.rou.xml": build_routes_scenario_xml("intervention_ready"),
        "urban_grid.sumocfg": build_urban_grid_sumocfg(),
        "viewsettings.xml": build_viewsettings_xml(),
    }

    for filename, content in files.items():
        filepath = SUMO_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated: {filepath.name} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
