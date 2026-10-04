"""NeetCode-style roadmap layout and edges."""

# Node top-left positions inside a 1000 x 1160 viewBox.
NODE_W = 176
NODE_H = 84

ROADMAP_NODES = [
    {"name": "Arrays & Hashing", "x": 380, "y": 20},
    {"name": "Two Pointers", "x": 210, "y": 150},
    {"name": "Stack", "x": 560, "y": 150},
    {"name": "Binary Search", "x": 40, "y": 300},
    {"name": "Sliding Window", "x": 250, "y": 300},
    {"name": "Linked List", "x": 460, "y": 300},
    {"name": "Trees", "x": 250, "y": 450},
    {"name": "Tries", "x": 40, "y": 600},
    {"name": "Heap / Priority Queue", "x": 250, "y": 600},
    {"name": "Backtracking", "x": 520, "y": 600},
    {"name": "Intervals", "x": 20, "y": 760},
    {"name": "Greedy", "x": 210, "y": 760},
    {"name": "Advanced Graphs", "x": 400, "y": 760},
    {"name": "Graphs", "x": 590, "y": 760},
    {"name": "1-D Dynamic Programming", "x": 780, "y": 760},
    {"name": "2-D Dynamic Programming", "x": 560, "y": 920},
    {"name": "Bit Manipulation", "x": 780, "y": 920},
    {"name": "Math & Geometry", "x": 620, "y": 1070},
]

ROADMAP_EDGES = [
    ("Arrays & Hashing", "Two Pointers"),
    ("Arrays & Hashing", "Stack"),
    ("Two Pointers", "Binary Search"),
    ("Two Pointers", "Sliding Window"),
    ("Two Pointers", "Linked List"),
    ("Binary Search", "Trees"),
    ("Sliding Window", "Trees"),
    ("Linked List", "Trees"),
    ("Trees", "Tries"),
    ("Trees", "Heap / Priority Queue"),
    ("Trees", "Backtracking"),
    ("Heap / Priority Queue", "Intervals"),
    ("Heap / Priority Queue", "Greedy"),
    ("Heap / Priority Queue", "Advanced Graphs"),
    ("Backtracking", "Graphs"),
    ("Backtracking", "1-D Dynamic Programming"),
    ("Graphs", "Advanced Graphs"),
    ("Graphs", "2-D Dynamic Programming"),
    ("1-D Dynamic Programming", "2-D Dynamic Programming"),
    ("1-D Dynamic Programming", "Bit Manipulation"),
    ("2-D Dynamic Programming", "Math & Geometry"),
    ("Bit Manipulation", "Math & Geometry"),
]


def edge_path(x1, y1, x2, y2):
    """Cubic curve from bottom-center of source to top-center of target."""
    mid_y = (y1 + y2) / 2
    return f"M {x1:.1f} {y1:.1f} C {x1:.1f} {mid_y:.1f}, {x2:.1f} {mid_y:.1f}, {x2:.1f} {y2:.1f}"


def build_roadmap_edges(nodes_by_name):
    edges = []
    for source, target in ROADMAP_EDGES:
        a = nodes_by_name[source]
        b = nodes_by_name[target]
        x1 = a["x"] + NODE_W / 2
        y1 = a["y"] + NODE_H
        x2 = b["x"] + NODE_W / 2
        y2 = b["y"]
        edges.append(
            {
                "source": source,
                "target": target,
                "path": edge_path(x1, y1, x2, y2),
            }
        )
    return edges
