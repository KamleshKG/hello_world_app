"""
code_layout.py  —  Simple hierarchical layout for code analysis diagrams
Positions class nodes in a grid / layered arrangement so arrows don't
all pile up in one corner.
"""

def auto_layout(class_names: list, cols: int = 4,
                col_w: int = 280, row_h: int = 220,
                start_x: int = 60, start_y: int = 80) -> dict:
    """
    Returns {class_name: (x, y)} for each name.
    Simple left-to-right, top-to-bottom grid.
    For ≤ 6 classes uses 2 columns; for more uses `cols`.
    """
    n = len(class_names)
    if n == 0:
        return {}
    if n <= 3:
        cols = 1
    elif n <= 6:
        cols = 2
    elif n <= 12:
        cols = 3
    else:
        cols = 4

    positions = {}
    for i, name in enumerate(class_names):
        col = i % cols
        row = i // cols
        x = start_x + col * col_w
        y = start_y + row * row_h
        positions[name] = (x, y)

    return positions
