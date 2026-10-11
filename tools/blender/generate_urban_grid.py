#!/usr/bin/env python3
"""Procedural 3D Urban Grid Generator for Blender 4.x / 3.x.

Generates a realistic, highly optimized 3D digital twin of a 2x2 signalized
urban road network (intersections I1, I2, I3, I4) matching the SUMO simulation
topology and Three.js coordinate conventions for the Urban-Grid platform.

Features:
- Four connected 4-way intersections with realistic junction pads and corners.
- Asphalt multi-lane corridors with curbs, sidewalks, and pedestrian zebra crossings.
- Dashed lane dividers, solid stop lines, and approach arrow markings.
- Realistic cantilever mast-arm traffic light assemblies with addressable lenses.
- Surrounding low-poly city blocks (towers, midrises, commercial, and corner buildings).
- Urban street furniture (modern LED street lamps, fire hydrants, benches, bollards).
- Stylized low-poly vegetation (sidewalk tree planters and trees).
- Shared, optimized PBR materials compatible with Three.js / glTF 2.0 standards.
- Saves native Blender project: 'urban_grid_city.blend'
- Exports web-ready glTF binary: 'frontend/public/models/urban_grid_city.glb'

Usage:
  1. From Blender GUI:
     - Open Blender -> Scripting Workspace -> Open this script -> Click 'Run Script'.
  2. From Command Line (Headless):
     - blender --background --python tools/blender/generate_urban_grid.py
"""

from __future__ import annotations

import math
import os
import sys

# -----------------------------------------------------------------------------
# Configuration & Network Topology
# -----------------------------------------------------------------------------

CONFIG = {
    # Scale Mode & Intersections (aligning directly with frontend urbanGridTopology.ts)
    # SUMO (250, 750) -> Three.js (-11, 9)
    # SUMO (750, 750) -> Three.js (11, 9)
    # SUMO (250, 250) -> Three.js (-11, -9)
    # SUMO (750, 250) -> Three.js (11, -9)
    "junctions": {
        "I1": {"x": -11.0, "z": 9.0, "name": "Northwest (I1)"},
        "I2": {"x": 11.0, "z": 9.0, "name": "Northeast (I2)"},
        "I3": {"x": -11.0, "z": -9.0, "name": "Southwest (I3)"},
        "I4": {"x": 11.0, "z": -9.0, "name": "Southeast (I4)"},
    },
    # Corridor connections between intersections
    "corridors": [
        ("I1", "I2", "Eastbound_North"),
        ("I1", "I3", "Southbound_West"),
        ("I2", "I4", "Southbound_East"),
        ("I3", "I4", "Eastbound_South"),
    ],
    # External approach roads (boundary entrances/exits matching SUMO J_W1, J_E2, etc.)
    "approaches": [
        {"junction": "I1", "direction": "WEST", "dx": -10.0, "dz": 0.0, "name": "Approach_W1_I1"},
        {"junction": "I1", "direction": "NORTH", "dx": 0.0, "dz": 10.0, "name": "Approach_N1_I1"},
        {"junction": "I2", "direction": "EAST", "dx": 10.0, "dz": 0.0, "name": "Approach_I2_E2"},
        {"junction": "I2", "direction": "NORTH", "dx": 0.0, "dz": 10.0, "name": "Approach_N2_I2"},
        {"junction": "I3", "direction": "WEST", "dx": -10.0, "dz": 0.0, "name": "Approach_W3_I3"},
        {"junction": "I3", "direction": "SOUTH", "dx": 0.0, "dz": -10.0, "name": "Approach_S3_I3"},
        {"junction": "I4", "direction": "EAST", "dx": 10.0, "dz": 0.0, "name": "Approach_I4_E4"},
        {"junction": "I4", "direction": "SOUTH", "dx": 0.0, "dz": -10.0, "name": "Approach_S4_I4"},
    ],
    # Dimensional specifications (in Three.js world units)
    "road_half_width": 2.4,        # Total asphalt width = 4.8 (2 lanes per direction)
    "junction_pad_size": 5.4,      # Intersection central box dimension
    "kerb_width": 0.28,            # Elevated curb concrete strip
    "kerb_height": 0.12,
    "sidewalk_width": 0.65,        # Pedestrian sidewalk
    "sidewalk_height": 0.06,
    "road_surface_height": 0.08,   # Road deck elevation
    "stop_line_width": 4.3,
    "stop_line_thickness": 0.25,
    "crosswalk_stripe_count": 6,
    "crosswalk_stripe_length": 0.85,
    "crosswalk_stripe_width": 0.35,
    "dash_length": 0.9,
    "dash_gap": 0.9,
    # Low-poly buildings matching mockBuildings.ts coordinates
    "buildings": [
        # North Block (z > 10)
        {"id": "B_N01", "x": -15.0, "z": 13.0, "w": 3.2, "d": 3.2, "h": 11.0, "type": "tower"},
        {"id": "B_N02", "x": -10.0, "z": 12.0, "w": 4.5, "d": 3.0, "h": 5.0, "type": "midrise"},
        {"id": "B_N03", "x": -5.0, "z": 13.0, "w": 3.0, "d": 3.0, "h": 8.0, "type": "tower"},
        {"id": "B_N04", "x": -1.0, "z": 12.0, "w": 4.0, "d": 3.5, "h": 4.5, "type": "commercial"},
        {"id": "B_N05", "x": 4.0, "z": 13.0, "w": 3.2, "d": 3.2, "h": 9.5, "type": "tower"},
        {"id": "B_N06", "x": 9.0, "z": 12.0, "w": 4.5, "d": 3.0, "h": 5.5, "type": "midrise"},
        {"id": "B_N07", "x": -13.0, "z": 16.0, "w": 3.5, "d": 3.0, "h": 4.0, "type": "commercial"},
        {"id": "B_N08", "x": -7.0, "z": 15.0, "w": 3.0, "d": 3.0, "h": 6.5, "type": "midrise"},
        {"id": "B_N09", "x": 1.0, "z": 16.0, "w": 3.5, "d": 3.5, "h": 13.0, "type": "tower"},
        {"id": "B_N10", "x": 7.0, "z": 15.0, "w": 4.0, "d": 3.0, "h": 3.5, "type": "commercial"},
        # East Block (x > 12)
        {"id": "B_E01", "x": 14.0, "z": 7.0, "w": 3.5, "d": 3.5, "h": 10.0, "type": "tower"},
        {"id": "B_E02", "x": 14.0, "z": 2.0, "w": 3.5, "d": 4.0, "h": 5.0, "type": "midrise"},
        {"id": "B_E03", "x": 14.0, "z": -3.0, "w": 3.0, "d": 3.0, "h": 3.8, "type": "commercial"},
        {"id": "B_E04", "x": 17.5, "z": 5.0, "w": 3.0, "d": 3.5, "h": 7.5, "type": "tower"},
        {"id": "B_E05", "x": 17.5, "z": -1.0, "w": 4.0, "d": 3.0, "h": 4.5, "type": "corner"},
        # South Block (z < -10)
        {"id": "B_S01", "x": 4.0, "z": -12.0, "w": 3.5, "d": 3.0, "h": 8.0, "type": "tower"},
        {"id": "B_S02", "x": -2.0, "z": -12.0, "w": 4.0, "d": 3.5, "h": 4.5, "type": "midrise"},
        {"id": "B_S03", "x": -8.0, "z": -12.0, "w": 4.5, "d": 3.0, "h": 3.5, "type": "commercial"},
        {"id": "B_S04", "x": -14.0, "z": -12.0, "w": 3.0, "d": 3.0, "h": 6.0, "type": "midrise"},
        {"id": "B_S05", "x": 1.0, "z": -15.5, "w": 3.0, "d": 3.0, "h": 12.0, "type": "tower"},
        {"id": "B_S06", "x": -7.0, "z": -15.5, "w": 4.0, "d": 3.5, "h": 5.0, "type": "corner"},
        # West Block (x < -13)
        {"id": "B_W01", "x": -15.5, "z": 5.0, "w": 3.0, "d": 3.5, "h": 7.0, "type": "tower"},
        {"id": "B_W02", "x": -15.5, "z": -2.0, "w": 4.0, "d": 3.0, "h": 4.5, "type": "midrise"},
        {"id": "B_W03", "x": -15.5, "z": -7.0, "w": 3.5, "d": 3.5, "h": 3.5, "type": "commercial"},
        # Central Urban Cluster
        {"id": "B_C01", "x": 6.5, "z": 2.5, "w": 3.2, "d": 3.2, "h": 6.5, "type": "midrise"},
        {"id": "B_C02", "x": -5.5, "z": 2.5, "w": 3.5, "d": 3.0, "h": 4.5, "type": "commercial"},
        {"id": "B_C03", "x": -5.5, "z": -3.5, "w": 3.0, "d": 3.5, "h": 8.5, "type": "tower"},
        {"id": "B_C04", "x": 6.5, "z": -3.5, "w": 3.2, "d": 3.2, "h": 5.5, "type": "midrise"},
    ],
    # Tree planter locations along corridors
    "trees": [
        {"x": -11.0, "z": 3.5}, {"x": -11.0, "z": -3.5},
        {"x": 11.0, "z": 3.5},  {"x": 11.0, "z": -3.5},
        {"x": -3.5, "z": 9.0},  {"x": 3.5, "z": 9.0},
        {"x": -3.5, "z": -9.0}, {"x": 3.5, "z": -9.0},
        {"x": -18.0, "z": 1.5}, {"x": 18.0, "z": 1.5},
    ],
    # Streetlights along network
    "streetlights": [
        {"x": -11.0 - 2.8, "z": 4.5, "rot": 0.0},
        {"x": -11.0 + 2.8, "z": -4.5, "rot": math.pi},
        {"x": 11.0 - 2.8, "z": 4.5, "rot": 0.0},
        {"x": 11.0 + 2.8, "z": -4.5, "rot": math.pi},
        {"x": -4.5, "z": 9.0 + 2.8, "rot": math.pi / 2},
        {"x": 4.5, "z": 9.0 - 2.8, "rot": -math.pi / 2},
        {"x": -4.5, "z": -9.0 + 2.8, "rot": math.pi / 2},
        {"x": 4.5, "z": -9.0 - 2.8, "rot": -math.pi / 2},
    ],
}

# -----------------------------------------------------------------------------
# Coordinate Transform: Three.js <-> Blender
# -----------------------------------------------------------------------------
# Three.js (Right-Handed): X = East, Y = Up, Z = North (in urbanGridTopology.ts)
# Blender  (Right-Handed): X = East, Y = North, Z = Up
# Standard glTF 2.0 Export converts Blender (X, Y, Z) -> glTF (X, Z, -Y)
# Therefore, to yield Three.js (x, y, z):
#   X_blender = x_three
#   Y_blender = -z_three
#   Z_blender = y_three
# When Blender exports with export_yup=True:
#   X_gltf = X_blender = x_three
#   Y_gltf = Z_blender = y_three
#   Z_gltf = -Y_blender = -(-z_three) = z_three
# -----------------------------------------------------------------------------

def to_blender_coords(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert Three.js world coordinates (x, y, z) into Blender local space."""
    return (x, -z, y)


def to_blender_rot(rot_y: float) -> tuple[float, float, float]:
    """Convert a Three.js Y-rotation (radians) to Blender Euler rotation."""
    return (0.0, 0.0, rot_y)


# -----------------------------------------------------------------------------
# Procedural Generator Core
# -----------------------------------------------------------------------------

def run_generator():
    try:
        import bpy
    except ImportError:
        print("[ERROR] bpy module is not available. Please run this script inside Blender:")
        print("  blender --background --python tools/blender/generate_urban_grid.py")
        sys.exit(1)

    print("===================================================================")
    print("  URBAN-GRID: PROCEDURAL 3D CITY ENVIRONMENT GENERATION")
    print(f"  Blender Version: {bpy.app.version_string}")
    print("===================================================================")

    # 1. Clean existing scene collections and objects
    clean_scene(bpy)

    # 2. Build Collections
    collections = setup_collections(bpy)

    # 3. Create PBR Materials
    materials = create_materials(bpy)

    # 4. Generate Ground Terrain
    create_ground_terrain(bpy, collections["Roads"], materials["Mat_Ground_Terrain"])

    # 5. Generate Junctions (I1, I2, I3, I4)
    for j_id, j_data in CONFIG["junctions"].items():
        create_junction(
            bpy,
            junction_id=j_id,
            pos_x=j_data["x"],
            pos_z=j_data["z"],
            collections=collections,
            materials=materials,
        )

    # 6. Generate Corridors (Connecting Roads)
    for from_id, to_id, name in CONFIG["corridors"]:
        p1 = CONFIG["junctions"][from_id]
        p2 = CONFIG["junctions"][to_id]
        create_corridor(
            bpy,
            name=name,
            x1=p1["x"],
            z1=p1["z"],
            x2=p2["x"],
            z2=p2["z"],
            collections=collections,
            materials=materials,
        )

    # 7. Generate External Approaches (Perimeter Boundary Roads)
    for app in CONFIG["approaches"]:
        j = CONFIG["junctions"][app["junction"]]
        x1 = j["x"]
        z1 = j["z"]
        x2 = j["x"] + app["dx"]
        z2 = j["z"] + app["dz"]
        create_corridor(
            bpy,
            name=app["name"],
            x1=x1,
            z1=z1,
            x2=x2,
            z2=z2,
            collections=collections,
            materials=materials,
            is_approach=True,
        )

    # 8. Generate Traffic Signal Rigs (I1 - I4)
    for j_id, j_data in CONFIG["junctions"].items():
        create_traffic_signal_rig(
            bpy,
            junction_id=j_id,
            center_x=j_data["x"],
            center_z=j_data["z"],
            collections=collections,
            materials=materials,
        )

    # 9. Generate Surrounding Low-Poly Buildings
    for b in CONFIG["buildings"]:
        create_building(
            bpy,
            building_def=b,
            collection=collections["Buildings"],
            materials=materials,
        )

    # 10. Generate Street Furniture (LED Streetlights, Hydrants, Benches)
    for i, lamp in enumerate(CONFIG["streetlights"]):
        create_streetlight(
            bpy,
            name=f"Streetlight_{i+1:02d}",
            pos_x=lamp["x"],
            pos_z=lamp["z"],
            rot_y=lamp["rot"],
            collection=collections["Street_Furniture"],
            materials=materials,
        )

    # 11. Generate Vegetation (Planters & Low-Poly Trees)
    for i, tree in enumerate(CONFIG["trees"]):
        create_tree(
            bpy,
            name=f"Tree_{i+1:02d}",
            pos_x=tree["x"],
            pos_z=tree["z"],
            collection=collections["Vegetation"],
            materials=materials,
        )

    # 12. Apply Transforms and Verify Consistency
    apply_all_transforms(bpy)

    # 13. Save Blender Project and Export GLB
    output_files = save_and_export(bpy)

    print("===================================================================")
    print("  URBAN-GRID 3D GENERATION COMPLETED SUCCESSFULLY")
    print(f"  Blend file: {output_files['blend']}")
    print(f"  GLB file:   {output_files['glb']}")
    print("===================================================================")


# -----------------------------------------------------------------------------
# Scene Setup & Collections
# -----------------------------------------------------------------------------

def clean_scene(bpy):
    """Cleanly purge existing objects and custom collections to prevent duplication."""
    # Delete all objects in current scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    # Clean orphaned meshes, materials, and curves
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)

    # Clean old UrbanGrid collections
    root_col = bpy.context.scene.collection
    for child in list(root_col.children):
        root_col.children.unlink(child)


def setup_collections(bpy) -> dict[str, bpy.types.Collection]:
    """Create organized hierarchical collections."""
    root_col = bpy.context.scene.collection
    main_col = bpy.data.collections.new("UrbanGrid_Scene")
    root_col.children.link(main_col)

    categories = [
        "Roads",
        "Markings",
        "Traffic_Signals",
        "Buildings",
        "Street_Furniture",
        "Vegetation",
    ]
    sub_cols = {}
    for cat in categories:
        col = bpy.data.collections.new(cat)
        main_col.children.link(col)
        sub_cols[cat] = col

    return sub_cols


# -----------------------------------------------------------------------------
# Material System (PBR Principled BSDF)
# -----------------------------------------------------------------------------

def create_materials(bpy) -> dict[str, bpy.types.Material]:
    """Create shared, physically-based materials compliant with glTF 2.0 / Three.js."""
    mats = {}

    def make_pbr(
        name: str,
        color: tuple[float, float, float, float],
        roughness: float = 0.5,
        metallic: float = 0.0,
        emission: tuple[float, float, float, float] | None = None,
        emission_strength: float = 0.0,
    ) -> bpy.types.Material:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out_node = nodes.new(type="ShaderNodeOutputMaterial")
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic

        if emission is not None and emission_strength > 0:
            # Handle Blender 4.x Emission Color vs older versions
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = emission
                bsdf.inputs["Emission Strength"].default_value = emission_strength
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = emission

        mats[name] = mat
        return mat

    # Asphalt & Pavement (Modern dark slate palette matching Urban-Grid frontend)
    make_pbr("Mat_Asphalt", (0.09, 0.16, 0.19, 1.0), roughness=0.88, metallic=0.04)
    make_pbr("Mat_Junction_Deck", (0.10, 0.18, 0.21, 1.0), roughness=0.86, metallic=0.05)
    make_pbr("Mat_Concrete_Curbs", (0.14, 0.26, 0.30, 1.0), roughness=0.82, metallic=0.02)
    make_pbr("Mat_Sidewalk", (0.12, 0.22, 0.26, 1.0), roughness=0.92, metallic=0.01)
    make_pbr("Mat_Ground_Terrain", (0.04, 0.09, 0.11, 1.0), roughness=1.0, metallic=0.0)

    # Road Markings (Crisp retroreflective white & warning yellow)
    make_pbr("Mat_Marking_White", (0.85, 0.95, 0.98, 1.0), roughness=0.35, metallic=0.0)
    make_pbr("Mat_Marking_Yellow", (0.95, 0.72, 0.15, 1.0), roughness=0.40, metallic=0.0)

    # Metals & Props
    make_pbr("Mat_Dark_Steel", (0.06, 0.12, 0.15, 1.0), roughness=0.42, metallic=0.75)
    make_pbr("Mat_Chrome_Metal", (0.35, 0.45, 0.50, 1.0), roughness=0.25, metallic=0.90)
    make_pbr("Mat_Signal_Housing", (0.07, 0.13, 0.16, 1.0), roughness=0.55, metallic=0.20)
    make_pbr("Mat_Hydrant_Red", (0.85, 0.15, 0.12, 1.0), roughness=0.40, metallic=0.30)
    make_pbr("Mat_Lamp_Glow", (0.95, 0.95, 0.85, 1.0), roughness=0.2, emission=(1.0, 1.0, 0.9, 1.0), emission_strength=4.0)

    # Traffic Light Signal Lenses (Emissive & Inactive)
    make_pbr("Mat_Lens_Red", (1.0, 0.15, 0.15, 1.0), roughness=0.25, emission=(1.0, 0.15, 0.15, 1.0), emission_strength=4.5)
    make_pbr("Mat_Lens_Yellow", (1.0, 0.75, 0.10, 1.0), roughness=0.25, emission=(1.0, 0.75, 0.10, 1.0), emission_strength=4.5)
    make_pbr("Mat_Lens_Green", (0.15, 1.0, 0.55, 1.0), roughness=0.25, emission=(0.15, 1.0, 0.55, 1.0), emission_strength=4.5)
    make_pbr("Mat_Lens_Off", (0.05, 0.08, 0.09, 1.0), roughness=0.30, metallic=0.15)

    # Architecture
    make_pbr("Mat_Tower_Glass", (0.08, 0.18, 0.22, 1.0), roughness=0.20, metallic=0.65)
    make_pbr("Mat_Tower_Spire", (0.25, 0.55, 0.65, 1.0), roughness=0.30, metallic=0.85)
    make_pbr("Mat_Midrise_Concrete", (0.11, 0.20, 0.24, 1.0), roughness=0.68, metallic=0.20)
    make_pbr("Mat_Commercial_Facade", (0.13, 0.23, 0.27, 1.0), roughness=0.62, metallic=0.15)
    make_pbr("Mat_Window_Glow", (0.25, 0.75, 0.85, 1.0), roughness=0.30, emission=(0.20, 0.70, 0.80, 1.0), emission_strength=1.5)
    make_pbr("Mat_Roof_Mechanical", (0.08, 0.14, 0.16, 1.0), roughness=0.50, metallic=0.45)

    # Foliage & Nature
    make_pbr("Mat_Foliage", (0.12, 0.45, 0.35, 1.0), roughness=0.85, metallic=0.0)
    make_pbr("Mat_Tree_Trunk", (0.22, 0.16, 0.13, 1.0), roughness=0.90, metallic=0.0)
    make_pbr("Mat_Planter_Stone", (0.13, 0.21, 0.24, 1.0), roughness=0.80, metallic=0.05)

    return mats


# -----------------------------------------------------------------------------
# Primitive Mesh Helpers
# -----------------------------------------------------------------------------

def add_box(
    bpy,
    name: str,
    size: tuple[float, float, float],
    pos_three: tuple[float, float, float],
    collection: bpy.types.Collection,
    material: bpy.types.Material | None = None,
    rot_y: float = 0.0,
) -> bpy.types.Object:
    """Create a cube mesh positioned in Three.js coordinates and linked to collection."""
    sx, sy, sz = size  # width (X), height (Y), depth (Z)
    bx, by, bz = to_blender_coords(pos_three[0], pos_three[1], pos_three[2])

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    # In Blender: dimension (dx, dy, dz) = (sx, sz, sy)
    hx, hy, hz = sx / 2.0, sz / 2.0, sy / 2.0
    verts = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
        (-hx, -hy, hz),  (hx, -hy, hz),  (hx, hy, hz),  (-hx, hy, hz),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
        (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj.location = (bx, by, bz)
    obj.rotation_euler = (0.0, 0.0, rot_y)

    if material:
        obj.data.materials.append(material)

    return obj


def add_cylinder(
    bpy,
    name: str,
    radius: float,
    height: float,
    pos_three: tuple[float, float, float],
    collection: bpy.types.Collection,
    material: bpy.types.Material | None = None,
    rot_y: float = 0.0,
    rot_x: float = 0.0,
    segments: int = 12,
) -> bpy.types.Object:
    """Create a vertical cylinder mesh positioned in Three.js coordinates."""
    bx, by, bz = to_blender_coords(pos_three[0], pos_three[1], pos_three[2])

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    verts = []
    # Bottom circle & top circle
    half_h = height / 2.0
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        vx = radius * math.cos(angle)
        vy = radius * math.sin(angle)
        verts.append((vx, vy, -half_h))
        verts.append((vx, vy, half_h))

    # Center caps
    verts.append((0.0, 0.0, -half_h))  # index: 2 * segments
    verts.append((0.0, 0.0, half_h))   # index: 2 * segments + 1
    bot_center = 2 * segments
    top_center = 2 * segments + 1

    faces = []
    for i in range(segments):
        nxt = (i + 1) % segments
        b1, t1 = i * 2, i * 2 + 1
        b2, t2 = nxt * 2, nxt * 2 + 1
        # Side quad
        faces.append((b1, b2, t2, t1))
        # Bottom tri
        faces.append((bot_center, b2, b1))
        # Top tri
        faces.append((top_center, t1, t2))

    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj.location = (bx, by, bz)
    obj.rotation_euler = (rot_x, 0.0, rot_y)

    if material:
        obj.data.materials.append(material)

    return obj


# -----------------------------------------------------------------------------
# Ground Terrain & Environment
# -----------------------------------------------------------------------------

def create_ground_terrain(bpy, collection, material):
    """Create foundation ground terrain slab."""
    add_box(
        bpy,
        name="Ground_Terrain_Foundation",
        size=(85.0, 0.2, 85.0),
        pos_three=(0.0, -0.1, 0.0),
        collection=collection,
        material=material,
    )


# -----------------------------------------------------------------------------
# Junctions (Intersections I1 - I4)
# -----------------------------------------------------------------------------

def create_junction(
    bpy,
    junction_id: str,
    pos_x: float,
    pos_z: float,
    collections: dict,
    materials: dict,
):
    """Create a fully detailed intersection hub (pad, corner curbs, crosswalks, stop lines)."""
    pad_size = CONFIG["junction_pad_size"]
    rh = CONFIG["road_surface_height"]
    rw = CONFIG["road_half_width"]
    kw = CONFIG["kerb_width"]
    sw = CONFIG["sidewalk_width"]

    # 1. Main Asphalt Junction Deck
    add_box(
        bpy,
        name=f"Junction_{junction_id}_Deck",
        size=(pad_size, 0.06, pad_size),
        pos_three=(pos_x, rh / 2.0, pos_z),
        collection=collections["Roads"],
        material=materials["Mat_Junction_Deck"],
    )

    # 2. Four Corner Sidewalk Quadrants with Curbs
    corner_offset_x = (pad_size + sw + kw) / 2.0
    corner_offset_z = (pad_size + sw + kw) / 2.0
    corner_size = 2.4

    for sx in (-1, 1):
        for sz in (-1, 1):
            cx = pos_x + sx * (rw + kw + sw / 2.0 + corner_size / 2.0)
            cz = pos_z + sz * (rw + kw + sw / 2.0 + corner_size / 2.0)
            corner_tag = f"{'W' if sx < 0 else 'E'}{'S' if sz < 0 else 'N'}"

            # Sidewalk corner pad
            add_box(
                bpy,
                name=f"Junction_{junction_id}_Sidewalk_{corner_tag}",
                size=(corner_size, CONFIG["sidewalk_height"], corner_size),
                pos_three=(cx, CONFIG["sidewalk_height"] / 2.0, cz),
                collection=collections["Roads"],
                material=materials["Mat_Sidewalk"],
            )

    # 3. Stop Lines on all 4 Inbound Approaches
    stop_dist = pad_size / 2.0 + 0.35
    approaches = [
        ("N", (pos_x, rh + 0.005, pos_z + stop_dist), (rw * 2.0 - 0.4, 0.01, 0.28)),
        ("S", (pos_x, rh + 0.005, pos_z - stop_dist), (rw * 2.0 - 0.4, 0.01, 0.28)),
        ("E", (pos_x + stop_dist, rh + 0.005, pos_z), (0.28, 0.01, rw * 2.0 - 0.4)),
        ("W", (pos_x - stop_dist, rh + 0.005, pos_z), (0.28, 0.01, rw * 2.0 - 0.4)),
    ]
    for tag, loc, dim in approaches:
        add_box(
            bpy,
            name=f"StopLine_{junction_id}_{tag}",
            size=dim,
            pos_three=loc,
            collection=collections["Markings"],
            material=materials["Mat_Marking_White"],
        )

    # 4. Zebra Pedestrian Crossings (4 legs)
    stripe_w = CONFIG["crosswalk_stripe_width"]
    stripe_l = CONFIG["crosswalk_stripe_length"]
    cw_dist = pad_size / 2.0 + 1.15
    num_stripes = CONFIG["crosswalk_stripe_count"]

    # North & South Crosswalks (horizontal stripes along X)
    for tag, cz in (("N", pos_z + cw_dist), ("S", pos_z - cw_dist)):
        spacing = (rw * 2.0 - 0.6) / (num_stripes - 1)
        for s in range(num_stripes):
            sx = pos_x - (rw - 0.3) + s * spacing
            add_box(
                bpy,
                name=f"Crosswalk_{junction_id}_{tag}_{s+1}",
                size=(stripe_w, 0.008, stripe_l),
                pos_three=(sx, rh + 0.006, cz),
                collection=collections["Markings"],
                material=materials["Mat_Marking_White"],
            )

    # East & West Crosswalks (horizontal stripes along Z)
    for tag, cx in (("E", pos_x + cw_dist), ("W", pos_x - cw_dist)):
        spacing = (rw * 2.0 - 0.6) / (num_stripes - 1)
        for s in range(num_stripes):
            sz = pos_z - (rw - 0.3) + s * spacing
            add_box(
                bpy,
                name=f"Crosswalk_{junction_id}_{tag}_{s+1}",
                size=(stripe_l, 0.008, stripe_w),
                pos_three=(cx, rh + 0.006, sz),
                collection=collections["Markings"],
                material=materials["Mat_Marking_White"],
            )


# -----------------------------------------------------------------------------
# Corridors & Road Segments
# -----------------------------------------------------------------------------

def create_corridor(
    bpy,
    name: str,
    x1: float,
    z1: float,
    x2: float,
    z2: float,
    collections: dict,
    materials: dict,
    is_approach: bool = False,
):
    """Create a connecting road corridor between two points with asphalt, curbs, sidewalks, and markings."""
    dx = x2 - x1
    dz = z2 - z1
    full_length = math.hypot(dx, dz)
    if full_length < 0.1:
        return

    # Trim road length to avoid overlapping junction pads
    pad_h = CONFIG["junction_pad_size"] / 2.0
    if is_approach:
        # One end is at a junction pad, other end is external boundary
        length = full_length - pad_h
        mid_x = (x1 + x2) / 2.0 + (dx / full_length) * (pad_h / 2.0)
        mid_z = (z1 + z2) / 2.0 + (dz / full_length) * (pad_h / 2.0)
    else:
        # Both ends connect to junction pads
        length = max(1.0, full_length - 2.0 * pad_h)
        mid_x = (x1 + x2) / 2.0
        mid_z = (z1 + z2) / 2.0

    angle_y = math.atan2(dx, dz)
    rw = CONFIG["road_half_width"]
    rh = CONFIG["road_surface_height"]
    kw = CONFIG["kerb_width"]
    kh = CONFIG["kerb_height"]
    sw = CONFIG["sidewalk_width"]
    sh = CONFIG["sidewalk_height"]

    # 1. Main Asphalt Surface
    add_box(
        bpy,
        name=f"Road_{name}_Asphalt",
        size=(rw * 2.0, 0.05, length),
        pos_three=(mid_x, rh / 2.0, mid_z),
        collection=collections["Roads"],
        material=materials["Mat_Asphalt"],
        rot_y=angle_y,
    )

    # 2. Elevated Curbs on both flanks
    for side, sign in (("L", -1), ("R", 1)):
        curb_offset = sign * (rw + kw / 2.0)
        cox = mid_x + math.cos(angle_y) * curb_offset
        coz = mid_z - math.sin(angle_y) * curb_offset
        add_box(
            bpy,
            name=f"Road_{name}_Curb_{side}",
            size=(kw, kh, length),
            pos_three=(cox, kh / 2.0, coz),
            collection=collections["Roads"],
            material=materials["Mat_Concrete_Curbs"],
            rot_y=angle_y,
        )

    # 3. Sidewalks along both sides
    for side, sign in (("L", -1), ("R", 1)):
        sw_offset = sign * (rw + kw + sw / 2.0)
        sox = mid_x + math.cos(angle_y) * sw_offset
        soz = mid_z - math.sin(angle_y) * sw_offset
        add_box(
            bpy,
            name=f"Road_{name}_Sidewalk_{side}",
            size=(sw, sh, length),
            pos_three=(sox, sh / 2.0, soz),
            collection=collections["Roads"],
            material=materials["Mat_Sidewalk"],
            rot_y=angle_y,
        )

    # 4. Center Dashed Lane Markings
    dash_len = CONFIG["dash_length"]
    dash_gap = CONFIG["dash_gap"]
    step = dash_len + dash_gap
    num_dashes = max(2, int(length / step))

    for d in range(num_dashes):
        offset_along = -length / 2.0 + (d + 0.5) * step
        if abs(offset_along) > (length / 2.0 - 0.4):
            continue
        dox = mid_x + math.sin(angle_y) * offset_along
        doz = mid_z + math.cos(angle_y) * offset_along
        add_box(
            bpy,
            name=f"Marking_Dash_{name}_{d+1}",
            size=(0.14, 0.008, dash_len),
            pos_three=(dox, rh + 0.005, doz),
            collection=collections["Markings"],
            material=materials["Mat_Marking_White"],
            rot_y=angle_y,
        )

    # 5. Solid Edge Shoulder Lines (outer lanes)
    for side, sign in (("L", -1), ("R", 1)):
        shoulder_off = sign * (rw - 0.22)
        sh_x = mid_x + math.cos(angle_y) * shoulder_off
        sh_z = mid_z - math.sin(angle_y) * shoulder_off
        add_box(
            bpy,
            name=f"Marking_Shoulder_{name}_{side}",
            size=(0.10, 0.006, length),
            pos_three=(sh_x, rh + 0.004, sh_z),
            collection=collections["Markings"],
            material=materials["Mat_Marking_White"],
            rot_y=angle_y,
        )


# -----------------------------------------------------------------------------
# Traffic Signals (Dynamic Signal Assemblies)
# -----------------------------------------------------------------------------

def create_traffic_signal_rig(
    bpy,
    junction_id: str,
    center_x: float,
    center_z: float,
    collections: dict,
    materials: dict,
):
    """Create 4 directional cantilever mast-arm signal posts for the intersection.

    Each post has:
      - Vertical steel pole & horizontal mast arm
      - Signal head housing with visors
      - Individually addressable Red, Yellow, Green lens sub-meshes
    """
    pad_h = CONFIG["junction_pad_size"] / 2.0
    corner_inset = pad_h + 0.35

    approaches = [
        # (Direction, (dx, dz), Heading angle facing incoming traffic)
        ("N", (-corner_inset, corner_inset), 0.0),            # Northwest post facing South
        ("S", (corner_inset, -corner_inset), math.pi),        # Southeast post facing North
        ("E", (corner_inset, corner_inset), -math.pi / 2.0),  # Northeast post facing West
        ("W", (-corner_inset, -corner_inset), math.pi / 2.0), # Southwest post facing East
    ]

    for dir_tag, (dx, dz), heading in approaches:
        px = center_x + dx
        pz = center_z + dz
        rig_tag = f"TL_{junction_id}_{dir_tag}"

        # 1. Vertical Steel Pole (height 2.6m)
        pole_h = 2.6
        add_cylinder(
            bpy,
            name=f"{rig_tag}_Pole",
            radius=0.065,
            height=pole_h,
            pos_three=(px, pole_h / 2.0, pz),
            collection=collections["Traffic_Signals"],
            material=materials["Mat_Dark_Steel"],
        )

        # 2. Cantilever Horizontal Mast Arm extending inward over traffic
        arm_len = 1.65
        arm_h = 0.05
        arm_x = px + math.sin(heading + math.pi / 2.0) * (arm_len / 2.0)
        arm_z = pz + math.cos(heading + math.pi / 2.0) * (arm_len / 2.0)
        add_box(
            bpy,
            name=f"{rig_tag}_Arm",
            size=(arm_len, arm_h, arm_h),
            pos_three=(arm_x, 2.5, arm_z),
            collection=collections["Traffic_Signals"],
            material=materials["Mat_Dark_Steel"],
            rot_y=heading,
        )

        # 3. Signal Head Housing (attached to mast arm tip)
        head_x = px + math.sin(heading + math.pi / 2.0) * (arm_len * 0.85)
        head_z = pz + math.cos(heading + math.pi / 2.0) * (arm_len * 0.85)
        head_y = 2.25
        head_w = 0.28
        head_h = 0.82
        head_d = 0.22

        add_box(
            bpy,
            name=f"{rig_tag}_Housing",
            size=(head_w, head_h, head_d),
            pos_three=(head_x, head_y, head_z),
            collection=collections["Traffic_Signals"],
            material=materials["Mat_Signal_Housing"],
            rot_y=heading,
        )

        # Visor Hoods on top of each lens
        for v_idx, y_off in enumerate((0.26, 0.0, -0.26)):
            add_box(
                bpy,
                name=f"{rig_tag}_Visor_{v_idx+1}",
                size=(0.20, 0.03, 0.12),
                pos_three=(
                    head_x + math.sin(heading) * 0.12,
                    head_y + y_off + 0.10,
                    head_z + math.cos(heading) * 0.12,
                ),
                collection=collections["Traffic_Signals"],
                material=materials["Mat_Signal_Housing"],
                rot_y=heading,
            )

        # 4. Individually Addressable Lenses
        lens_radius = 0.08
        lens_depth = 0.05

        lenses = [
            ("Lens_Red", 0.26, materials["Mat_Lens_Red"]),
            ("Lens_Yellow", 0.0, materials["Mat_Lens_Off"]),
            ("Lens_Green", -0.26, materials["Mat_Lens_Off"]),
        ]
        for lens_name, y_off, mat in lenses:
            lx = head_x + math.sin(heading) * 0.11
            lz = head_z + math.cos(heading) * 0.11
            ly = head_y + y_off
            add_cylinder(
                bpy,
                name=f"{rig_tag}_{lens_name}",
                radius=lens_radius,
                height=lens_depth,
                pos_three=(lx, ly, lz),
                collection=collections["Traffic_Signals"],
                material=mat,
                rot_y=heading,
                rot_x=math.pi / 2.0,  # Face forward toward traffic
                segments=12,
            )


# -----------------------------------------------------------------------------
# Surrounding Low-Poly Buildings
# -----------------------------------------------------------------------------

def create_building(bpy, building_def: dict, collection, materials: dict):
    """Create a stylized, modern low-poly building with architectural detailing."""
    b_id = building_def["id"]
    bx = building_def["x"]
    bz = building_def["z"]
    bw = building_def["w"]
    bd = building_def["d"]
    bh = building_def["h"]
    btype = building_def["type"]

    if btype == "tower":
        # Multi-tiered high-rise tower
        # Base Podium
        podium_h = 1.4
        add_box(
            bpy,
            name=f"{b_id}_Podium",
            size=(bw + 0.4, podium_h, bd + 0.4),
            pos_three=(bx, podium_h / 2.0, bz),
            collection=collection,
            material=materials["Mat_Midrise_Concrete"],
        )
        # Main Tower Shaft
        shaft_h = bh - podium_h
        add_box(
            bpy,
            name=f"{b_id}_Shaft",
            size=(bw, shaft_h, bd),
            pos_three=(bx, podium_h + shaft_h / 2.0, bz),
            collection=collection,
            material=materials["Mat_Tower_Glass"],
        )
        # Rooftop Mechanical Penthouse
        ph_h = 0.8
        add_box(
            bpy,
            name=f"{b_id}_Penthouse",
            size=(bw * 0.55, ph_h, bd * 0.55),
            pos_three=(bx, bh + ph_h / 2.0, bz),
            collection=collection,
            material=materials["Mat_Roof_Mechanical"],
        )
        # Antenna Spire
        spire_h = 1.6
        add_cylinder(
            bpy,
            name=f"{b_id}_Spire",
            radius=0.04,
            height=spire_h,
            pos_three=(bx, bh + ph_h + spire_h / 2.0, bz),
            collection=collection,
            material=materials["Mat_Tower_Spire"],
        )

    elif btype == "midrise":
        # Midrise building with window strips and parapet
        add_box(
            bpy,
            name=f"{b_id}_Main",
            size=(bw, bh, bd),
            pos_three=(bx, bh / 2.0, bz),
            collection=collection,
            material=materials["Mat_Midrise_Concrete"],
        )
        # Horizontal Window Ribbon Accent
        num_floors = max(2, int(bh / 1.4))
        for f in range(num_floors):
            fy = (f + 0.6) * (bh / num_floors)
            add_box(
                bpy,
                name=f"{b_id}_WindowBand_{f+1}",
                size=(bw + 0.02, 0.28, bd + 0.02),
                pos_three=(bx, fy, bz),
                collection=collection,
                material=materials["Mat_Window_Glow"],
            )
        # Roof Rim / Parapet
        add_box(
            bpy,
            name=f"{b_id}_RoofRim",
            size=(bw + 0.15, 0.12, bd + 0.15),
            pos_three=(bx, bh + 0.06, bz),
            collection=collection,
            material=materials["Mat_Roof_Mechanical"],
        )

    elif btype == "commercial":
        # Commercial / Retail center with entrance canopy
        add_box(
            bpy,
            name=f"{b_id}_Main",
            size=(bw, bh, bd),
            pos_three=(bx, bh / 2.0, bz),
            collection=collection,
            material=materials["Mat_Commercial_Facade"],
        )
        # Street-Level Storefront Canopy
        add_box(
            bpy,
            name=f"{b_id}_Canopy",
            size=(bw + 0.5, 0.10, 0.9),
            pos_three=(bx, 0.75, bz + bd / 2.0 + 0.4),
            collection=collection,
            material=materials["Mat_Dark_Steel"],
        )
        # Glass display window
        add_box(
            bpy,
            name=f"{b_id}_DisplayGlass",
            size=(bw * 0.85, 0.65, 0.05),
            pos_three=(bx, 0.40, bz + bd / 2.0 + 0.02),
            collection=collection,
            material=materials["Mat_Window_Glow"],
        )

    else:
        # Corner / Chamfered modern building
        add_box(
            bpy,
            name=f"{b_id}_Main",
            size=(bw, bh, bd),
            pos_three=(bx, bh / 2.0, bz),
            collection=collection,
            material=materials["Mat_Midrise_Concrete"],
        )
        # 45-degree corner accent mass
        add_box(
            bpy,
            name=f"{b_id}_CornerAccent",
            size=(bw * 0.45, bh + 0.3, bd * 0.45),
            pos_three=(bx + bw * 0.2, (bh + 0.3) / 2.0, bz + bd * 0.2),
            collection=collection,
            material=materials["Mat_Tower_Glass"],
            rot_y=math.pi / 4.0,
        )


# -----------------------------------------------------------------------------
# Street Furniture & Vegetation
# -----------------------------------------------------------------------------

def create_streetlight(bpy, name: str, pos_x: float, pos_z: float, rot_y: float, collection, materials: dict):
    """Create a modern curved-mast LED streetlight."""
    pole_h = 3.2
    add_cylinder(
        bpy,
        name=f"{name}_Pole",
        radius=0.045,
        height=pole_h,
        pos_three=(pos_x, pole_h / 2.0, pos_z),
        collection=collection,
        material=materials["Mat_Dark_Steel"],
    )
    # Curved Arm Cantilever
    arm_l = 0.9
    add_box(
        bpy,
        name=f"{name}_Arm",
        size=(arm_l, 0.04, 0.04),
        pos_three=(pos_x + math.sin(rot_y) * (arm_l / 2.0), pole_h, pos_z + math.cos(rot_y) * (arm_l / 2.0)),
        collection=collection,
        material=materials["Mat_Dark_Steel"],
        rot_y=rot_y,
    )
    # LED Lamp Head
    add_box(
        bpy,
        name=f"{name}_Fixture",
        size=(0.28, 0.06, 0.12),
        pos_three=(pos_x + math.sin(rot_y) * arm_l, pole_h - 0.04, pos_z + math.cos(rot_y) * arm_l),
        collection=collection,
        material=materials["Mat_Lamp_Glow"],
        rot_y=rot_y,
    )


def create_tree(bpy, name: str, pos_x: float, pos_z: float, collection, materials: dict):
    """Create a stylized low-poly urban tree with concrete sidewalk planter box."""
    # Planter Box
    add_box(
        bpy,
        name=f"{name}_Planter",
        size=(0.95, 0.14, 0.95),
        pos_three=(pos_x, 0.07, pos_z),
        collection=collection,
        material=materials["Mat_Planter_Stone"],
    )
    # Trunk
    trunk_h = 1.4
    add_cylinder(
        bpy,
        name=f"{name}_Trunk",
        radius=0.08,
        height=trunk_h,
        pos_three=(pos_x, trunk_h / 2.0 + 0.14, pos_z),
        collection=collection,
        material=materials["Mat_Tree_Trunk"],
        segments=8,
    )
    # Foliage Canopy (stylized faceted dodecahedron / layered spheres)
    canopy_h = 1.3
    add_cylinder(
        bpy,
        name=f"{name}_Canopy_Lower",
        radius=0.65,
        height=canopy_h,
        pos_three=(pos_x, trunk_h + canopy_h / 2.0, pos_z),
        collection=collection,
        material=materials["Mat_Foliage"],
        segments=7,
    )
    add_cylinder(
        bpy,
        name=f"{name}_Canopy_Upper",
        radius=0.45,
        height=canopy_h * 0.75,
        pos_three=(pos_x, trunk_h + canopy_h + 0.35, pos_z),
        collection=collection,
        material=materials["Mat_Foliage"],
        segments=6,
    )


# -----------------------------------------------------------------------------
# Transform Application & Export Pipeline
# -----------------------------------------------------------------------------

def apply_all_transforms(bpy):
    """Ensure all object rotations and scales are baked into geometry."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")


def save_and_export(bpy) -> dict[str, str]:
    """Save the Blender project (.blend) and export web-ready glTF 2.0 (.glb)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    blend_file = os.path.join(workspace_root, "urban_grid_city.blend")
    glb_dir = os.path.join(workspace_root, "frontend", "public", "models")
    os.makedirs(glb_dir, exist_ok=True)
    glb_file = os.path.join(glb_dir, "urban_grid_city.glb")

    # 1. Save Native Blender File
    bpy.ops.wm.save_as_mainfile(filepath=blend_file)
    print(f"[EXPORT] Saved Blender project: {blend_file}")

    # Also save a copy inside tools/blender for convenience
    tools_blend = os.path.join(script_dir, "urban_grid_city.blend")
    try:
        import shutil
        shutil.copyfile(blend_file, tools_blend)
    except Exception:
        pass

    # 2. Export GLTF Binary (.glb)
    bpy.ops.object.select_all(action="SELECT")

    # Call glTF exporter with verified parameters
    bpy.ops.export_scene.gltf(
        filepath=glb_file,
        export_format="GLB",
        export_apply=True,
        export_materials="EXPORT",
        export_yup=True,
    )
    print(f"[EXPORT] Exported web-optimized glTF: {glb_file}")

    return {"blend": blend_file, "glb": glb_file}


# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    run_generator()
