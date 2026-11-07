#!/usr/bin/env python3
"""Two-layer grid maze router (A*) for the Rev0 panel boards.

Small and dependency-free on purpose: the boards are sparse (switches, LEDs,
one header), so a 0.5 mm Lee/A* grid with clearance halos is enough to give
short-free copper on PCBWay's standard 6/6 mil process.

Geometry rules (mm):
  track 0.30, clearance >= 0.20, via 0.70 pad / 0.40 drill,
  grid 0.50 (adjacent parallel tracks therefore keep 0.20 clearance).
Top copper prefers horizontal runs, bottom copper vertical runs.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

GRID = 0.5
TRACK = 0.30
CLEAR = 0.20
VIA_PAD = 0.70
VIA_DRILL = 0.40
EDGE_KEEPOUT = 0.6
VIA_COST = 12
WRONG_WAY = 2  # cost multiplier for non-preferred direction

FREE = -1
BLOCK = -2


@dataclass
class Pad:
    x: float
    y: float
    diam: float
    net: str


@dataclass
class Route:
    net: str
    layer_paths: list[tuple[int, list[tuple[float, float]]]] = field(default_factory=list)
    vias: list[tuple[float, float]] = field(default_factory=list)


class Router:
    def __init__(self, width: float, height: float):
        self.w, self.h = width, height
        self.nx = int(math.floor(width / GRID)) + 1
        self.ny = int(math.floor(height / GRID)) + 1
        n = self.nx * self.ny
        # keepout owner per layer: FREE, BLOCK or net id
        self.keep = [[FREE] * n, [FREE] * n]
        # actual copper owner per layer (subset of keep)
        self.copper = [[FREE] * n, [FREE] * n]
        # cells where a via of a given net may NOT be placed (other-net owner)
        self.via_keep = [FREE] * n
        self.nets: dict[str, int] = {}
        self.pads: list[Pad] = []
        self.routes: list[Route] = []
        self.failed: list[str] = []
        m = int(math.ceil(EDGE_KEEPOUT / GRID))
        for iy in range(self.ny):
            for ix in range(self.nx):
                x, y = ix * GRID, iy * GRID
                if x < EDGE_KEEPOUT or y < EDGE_KEEPOUT or x > width - EDGE_KEEPOUT or y > height - EDGE_KEEPOUT:
                    i = self.idx(ix, iy)
                    self.keep[0][i] = self.keep[1][i] = BLOCK
                    self.via_keep[i] = BLOCK
        del m

    # ------------------------------------------------------------------ grid
    def idx(self, ix: int, iy: int) -> int:
        return iy * self.nx + ix

    def net_id(self, name: str) -> int:
        if name not in self.nets:
            self.nets[name] = len(self.nets)
        return self.nets[name]

    def _disc(self, x: float, y: float, r: float):
        r_c = int(math.ceil(r / GRID))
        cx, cy = int(round(x / GRID)), int(round(y / GRID))
        for iy in range(max(0, cy - r_c), min(self.ny - 1, cy + r_c) + 1):
            for ix in range(max(0, cx - r_c), min(self.nx - 1, cx + r_c) + 1):
                if math.hypot(ix * GRID - x, iy * GRID - y) < r:
                    yield self.idx(ix, iy)

    def _claim(self, arr: list[int], i: int, nid: int) -> None:
        cur = arr[i]
        if cur == FREE:
            arr[i] = nid
        elif cur != nid:
            arr[i] = BLOCK  # contested by two nets: nobody may route here

    # ------------------------------------------------------------ obstacles
    def add_pad(self, x: float, y: float, diam: float, net: str) -> None:
        nid = self.net_id(net)
        self.pads.append(Pad(x, y, diam, net))
        r = diam / 2
        for L in (0, 1):
            for i in self._disc(x, y, r + CLEAR + TRACK / 2):
                self._claim(self.keep[L], i, nid)
            for i in self._disc(x, y, max(r - TRACK / 2, GRID * 0.5)):
                self.copper[L][i] = nid
        for i in self._disc(x, y, r + CLEAR + VIA_PAD / 2):
            self._claim(self.via_keep, i, nid)

    def add_hole(self, x: float, y: float, diam: float) -> None:
        r = diam / 2 + 0.3 + TRACK / 2
        for L in (0, 1):
            for i in self._disc(x, y, r):
                self.keep[L][i] = BLOCK
        for i in self._disc(x, y, diam / 2 + 0.3 + VIA_PAD / 2):
            self.via_keep[i] = BLOCK

    def add_keepout_rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        for iy in range(self.ny):
            for ix in range(self.nx):
                x, y = ix * GRID, iy * GRID
                if x0 <= x <= x1 and y0 <= y <= y1:
                    i = self.idx(ix, iy)
                    self.keep[0][i] = self.keep[1][i] = BLOCK
                    self.via_keep[i] = BLOCK

    # --------------------------------------------------------------- search
    def _passable(self, L: int, i: int, nid: int) -> bool:
        k = self.keep[L][i]
        return k == FREE or k == nid

    def _via_ok(self, i: int, nid: int) -> bool:
        if not (self._passable(0, i, nid) and self._passable(1, i, nid)):
            return False
        vk = self.via_keep[i]
        return vk == FREE or vk == nid

    def route_net(self, net: str) -> bool:
        nid = self.nets[net]
        terms = [p for p in self.pads if p.net == net]
        if len(terms) < 2:
            return True
        # Connect pads one at a time to the growing tree (nearest first).
        tree_pads = [terms[0]]
        rest = terms[1:]
        route = Route(net)
        tree: set[tuple[int, int]] = {(L, i) for L in (0, 1) for i in self._pad_cells(terms[0])}
        while rest:
            rest.sort(key=lambda p: min(abs(p.x - q.x) + abs(p.y - q.y) for q in tree_pads))
            tgt = rest.pop(0)
            path = self._astar(nid, tgt, tree)
            if path is None:
                self.failed.append(net)
                return False
            self._commit(nid, path, route)
            tree.update(path)
            for L, i in route_vias_cells(self, path):
                tree.add((L, i))
            tree.update((L, i) for L in (0, 1) for i in self._pad_cells(tgt))
            tree_pads.append(tgt)
        self.routes.append(route)
        return True

    def _pad_cells(self, p: Pad) -> list[int]:
        return list(self._disc(p.x, p.y, max(p.diam / 2 - TRACK / 2, GRID * 0.5)))

    def _astar(self, nid: int, tgt: Pad, tree: set[tuple[int, int]]):
        nx = self.nx
        tx, ty = tgt.x / GRID, tgt.y / GRID
        tgt_cells = set(self._pad_cells(tgt))
        heap: list[tuple[float, int, int, int]] = []
        best: dict[tuple[int, int], int] = {}
        prev: dict[tuple[int, int], tuple[int, int] | None] = {}
        # sources: every copper cell of this net that is not inside the target pad
        for L, i in tree:
            if i not in tgt_cells:
                ix, iy = i % nx, i // nx
                h = abs(ix - tx) + abs(iy - ty)
                best[(L, i)] = 0
                prev[(L, i)] = None
                heapq.heappush(heap, (h, 0, L, i))
        if not heap:
            return None
        while heap:
            f, g, L, i = heapq.heappop(heap)
            if best.get((L, i), 1 << 30) < g:
                continue
            if i in tgt_cells:
                return self._unwind(prev, (L, i))
            ix, iy = i % nx, i // nx
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jx, jy = ix + dx, iy + dy
                if jx < 0 or jy < 0 or jx >= nx or jy >= self.ny:
                    continue
                j = jy * nx + jx
                if not self._passable(L, j, nid):
                    continue
                horiz = dy == 0
                step = 1 if (horiz and L == 0) or (not horiz and L == 1) else WRONG_WAY
                ng = g + step
                if ng < best.get((L, j), 1 << 30):
                    best[(L, j)] = ng
                    prev[(L, j)] = (L, i)
                    heapq.heappush(heap, (ng + abs(jx - tx) + abs(jy - ty), ng, L, j))
            # layer change through a via
            O = 1 - L
            if self._via_ok(i, nid):
                ng = g + VIA_COST
                if ng < best.get((O, i), 1 << 30):
                    best[(O, i)] = ng
                    prev[(O, i)] = (L, i)
                    heapq.heappush(heap, (ng + abs(ix - tx) + abs(iy - ty), ng, O, i))
        return None

    @staticmethod
    def _unwind(prev, node):
        out = []
        while node is not None:
            out.append(node)
            node = prev[node]
        out.reverse()
        return out

    def _commit(self, nid: int, path, route: Route) -> None:
        nx = self.nx
        seg_layer = path[0][0]
        seg: list[tuple[float, float]] = []
        for n, (L, i) in enumerate(path):
            x, y = (i % nx) * GRID, (i // nx) * GRID
            if L != seg_layer:
                if len(seg) > 1:
                    route.layer_paths.append((seg_layer, _simplify(seg)))
                route.vias.append((x, y))
                for c in self._disc(x, y, VIA_PAD / 2 + CLEAR + TRACK / 2):
                    self._claim(self.keep[0], c, nid)
                    self._claim(self.keep[1], c, nid)
                for c in self._disc(x, y, VIA_PAD + CLEAR):
                    self._claim(self.via_keep, c, nid)
                self.copper[0][i] = self.copper[1][i] = nid
                seg_layer = L
                seg = [(x, y)]
                continue
            seg.append((x, y))
            self.copper[L][i] = nid
            self.keep[L][i] = nid
            # neighbours of a track: no via of another net may sit next to it
            for c in self._disc(x, y, TRACK / 2 + CLEAR + VIA_PAD / 2):
                self._claim(self.via_keep, c, nid)
        if len(seg) > 1:
            route.layer_paths.append((seg_layer, _simplify(seg)))


def route_vias_cells(r: "Router", path):
    """Both-layer cells of every layer change in ``path`` (vias join the tree)."""
    for (La, ia), (Lb, ib) in zip(path, path[1:]):
        if La != Lb:
            yield (0, ia)
            yield (1, ia)


def _simplify(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for a, b in zip(pts[1:], pts[2:]):
        p = out[-1]
        if (a[0] - p[0]) * (b[1] - a[1]) - (a[1] - p[1]) * (b[0] - a[0]) != 0:
            out.append(a)
    out.append(pts[-1])
    return out
