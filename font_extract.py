#!/usr/bin/env python3
"""Extract a vector subset of Liberation Sans (Regular + Bold, SIL OFL)
from the system fonts into font_data.py.

Stdlib only. Reads /usr/share/fonts/truetype/liberation/*.ttf, parses the
TrueType outlines (glyf, quadratic splines), flattens them to polygons in
font units and writes them as Python literals. No font binary is downloaded
and no binary is shipped: only the extracted outlines of the characters the
poster actually needs.
"""
import json
import struct
import sys

FONTS = {
    "REGULAR": "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "BOLD": "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
}

CHARS = "".join(chr(c) for c in range(32, 127)) + "·—–‘’“”×−•"


def u16(b, o):
    return struct.unpack_from(">H", b, o)[0]


def i16(b, o):
    return struct.unpack_from(">h", b, o)[0]


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


class TTF:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        n = u16(self.data, 4)
        self.tables = {}
        for i in range(n):
            off = 12 + i * 16
            tag = self.data[off:off + 4].decode("latin1")
            self.tables[tag] = (u32(self.data, off + 8), u32(self.data, off + 12))
        head_off, _ = self.tables["head"]
        self.upm = u16(self.data, head_off + 18)
        self.loc_fmt = i16(self.data, head_off + 50)
        maxp_off, _ = self.tables["maxp"]
        self.num_glyphs = u16(self.data, maxp_off + 4)
        hhea_off, _ = self.tables["hhea"]
        self.num_hmetrics = u16(self.data, hhea_off + 34)
        self.cmap = self._parse_cmap()
        self.glyf_off, _ = self.tables["glyf"]
        self.loca_off, _ = self.tables["loca"]
        self.hmtx_off, _ = self.tables["hmtx"]

    def _parse_cmap(self):
        off, _ = self.tables["cmap"]
        n = u16(self.data, off + 2)
        best = None
        for i in range(n):
            plat = u16(self.data, off + 4 + i * 8)
            enc = u16(self.data, off + 6 + i * 8)
            sub = off + u32(self.data, off + 8 + i * 8)
            fmt = u16(self.data, sub)
            if fmt == 12 and (plat, enc) in ((3, 10), (0, 4)):
                return self._cmap12(sub)
            if fmt == 4 and best is None:
                best = sub
        if best is not None:
            return self._cmap4(best)
        raise ValueError("no usable cmap")

    def _cmap4(self, sub):
        seg_count = u16(self.data, sub + 6) // 2
        end_off = sub + 14
        start_off = end_off + 2 * seg_count + 2
        delta_off = start_off + 2 * seg_count
        range_off = delta_off + 2 * seg_count
        mapping = {}
        for i in range(seg_count):
            end = u16(self.data, end_off + 2 * i)
            start = u16(self.data, start_off + 2 * i)
            delta = i16(self.data, delta_off + 2 * i)
            ro = u16(self.data, range_off + 2 * i)
            for c in range(start, end + 1):
                if c == 0xFFFF:
                    continue
                if ro == 0:
                    g = (c + delta) & 0xFFFF
                else:
                    addr = range_off + 2 * i + ro + 2 * (c - start)
                    g = u16(self.data, addr)
                    if g:
                        g = (g + delta) & 0xFFFF
                if g:
                    mapping[c] = g
        return mapping

    def _cmap12(self, sub):
        n = u32(self.data, sub + 12)
        mapping = {}
        for i in range(n):
            o = sub + 16 + i * 12
            start, end, gid = u32(self.data, o), u32(self.data, o + 4), u32(self.data, o + 8)
            for c in range(start, end + 1):
                mapping[c] = gid + (c - start)
        return mapping

    def advance(self, gid):
        if gid < self.num_hmetrics:
            return u16(self.data, self.hmtx_off + gid * 4)
        return u16(self.data, self.hmtx_off + (self.num_hmetrics - 1) * 4)

    def glyph_offset(self, gid):
        if self.loc_fmt == 0:
            return u16(self.data, self.loca_off + gid * 2) * 2, \
                u16(self.data, self.loca_off + (gid + 1) * 2) * 2
        return (u32(self.data, self.loca_off + gid * 4),
                u32(self.data, self.loca_off + (gid + 1) * 4))

    def glyph_contours(self, gid, depth=0):
        """Return list of contours; each contour is a list of (x, y, on_curve)."""
        if depth > 3:
            return []
        o0, o1 = self.glyph_offset(gid)
        if o1 <= o0:
            return []
        o = self.glyf_off + o0
        n_cont = i16(self.data, o)
        if n_cont >= 0:
            ends = [u16(self.data, o + 10 + 2 * i) for i in range(n_cont)]
            n_pts = ends[-1] + 1 if ends else 0
            ins_len = u16(self.data, o + 10 + 2 * n_cont)
            p = o + 12 + 2 * n_cont + ins_len
            flags = []
            while len(flags) < n_pts:
                f = self.data[p]
                p += 1
                flags.append(f)
                if f & 0x08:
                    rep = self.data[p]
                    p += 1
                    flags.extend([f] * rep)
            xs, x = [], 0
            for f in flags:
                if f & 0x02:
                    dx = self.data[p]
                    p += 1
                    x += dx if (f & 0x10) else -dx
                elif not (f & 0x10):
                    x += i16(self.data, p)
                    p += 2
                xs.append(x)
            ys, y = [], 0
            for f in flags:
                if f & 0x04:
                    dy = self.data[p]
                    p += 1
                    y += dy if (f & 0x20) else -dy
                elif not (f & 0x20):
                    y += i16(self.data, p)
                    p += 2
                ys.append(y)
            contours, start = [], 0
            for end in ends:
                contours.append([(xs[i], ys[i], bool(flags[i] & 0x01))
                                 for i in range(start, end + 1)])
                start = end + 1
            return contours
        # compound glyph
        p = o + 10
        contours = []
        while True:
            comp_flags = u16(self.data, p)
            comp_gid = u16(self.data, p + 2)
            p += 4
            if comp_flags & 0x01:  # words
                a1 = i16(self.data, p)
                a2 = i16(self.data, p + 2)
                p += 4
            else:
                a1 = struct.unpack_from(">b", self.data, p)[0]
                a2 = struct.unpack_from(">b", self.data, p + 1)[0]
                p += 2
            if comp_flags & 0x02:  # args are xy
                dx, dy = a1, a2
            else:
                dx, dy = 0, 0
            sx = sy = 1.0
            m00 = m01 = m10 = m11 = None
            if comp_flags & 0x08:
                sx = sy = i16(self.data, p) / 16384.0
                p += 2
            elif comp_flags & 0x40:
                sx = i16(self.data, p) / 16384.0
                sy = i16(self.data, p + 2) / 16384.0
                p += 4
            elif comp_flags & 0x80:
                m00 = i16(self.data, p) / 16384.0
                m01 = i16(self.data, p + 2) / 16384.0
                m10 = i16(self.data, p + 4) / 16384.0
                m11 = i16(self.data, p + 6) / 16384.0
                p += 8
            for cont in self.glyph_contours(comp_gid, depth + 1):
                out = []
                for (x, y, on) in cont:
                    if m00 is not None:
                        nx = x * m00 + y * m01 + dx
                        ny = x * m10 + y * m11 + dy
                    else:
                        nx = x * sx + dx
                        ny = y * sy + dy
                    out.append((round(nx), round(ny), on))
                contours.append(out)
            if not (comp_flags & 0x20):
                break
        return contours


def flatten_quad(p0, p1, p2, tol, out, depth=0):
    """Flatten one quadratic Bezier; append polyline points (excluding p0)."""
    mx = (p0[0] + 2 * p1[0] + p2[0]) / 4.0
    my = (p0[1] + 2 * p1[1] + p2[1]) / 4.0
    ex = (p0[0] + p2[0]) / 2.0
    ey = (p0[1] + p2[1]) / 2.0
    if depth >= 10 or (abs(mx - ex) < tol and abs(my - ey) < tol):
        out.append((round(p2[0]), round(p2[1])))
        return
    q0 = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    q1 = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    mid = ((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2)
    flatten_quad(p0, q0, mid, tol, out, depth + 1)
    flatten_quad(mid, q1, p2, tol, out, depth + 1)


def flatten_contour(cont, tol=6.0):
    """Contour of (x, y, on) -> polygon [(x, y), ...] in font coords (y up)."""
    pts = list(cont)
    if not pts:
        return []
    # rotate so contour starts at an on-curve point
    if not pts[0][2]:
        if pts[-1][2]:
            pts = [pts[-1]] + pts[:-1]
        else:
            mx = (pts[0][0] + pts[-1][0]) // 2
            my = (pts[0][1] + pts[-1][1]) // 2
            pts = [(mx, my, True)] + pts
    poly = [(pts[0][0], pts[0][1])]
    i = 1
    n = len(pts)
    while i < n:
        p0 = poly[-1]
        p1 = pts[i]
        if p1[2]:
            poly.append((p1[0], p1[1]))
            i += 1
        else:
            if i + 1 < n:
                p2 = pts[i + 1]
                if p2[2]:
                    flatten_quad(p0, (p1[0], p1[1]), (p2[0], p2[1]), tol, poly)
                    i += 2
                else:
                    mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                    flatten_quad(p0, (p1[0], p1[1]), mid, tol, poly)
                    i += 1
            else:
                flatten_quad(p0, (p1[0], p1[1]), poly[0], tol, poly)
                i += 1
    # close: if last point != first, the closing edge is implicit
    return poly


def extract(path):
    ttf = TTF(path)
    out = {}
    missing = []
    for ch in CHARS:
        gid = ttf.cmap.get(ord(ch))
        if gid is None:
            missing.append(ch)
            continue
        contours = ttf.glyph_contours(gid)
        polys = []
        for cont in contours:
            poly = flatten_contour(cont)
            if len(poly) >= 3:
                flat = []
                for (x, y) in poly:
                    flat.append(x)
                    flat.append(y)
                polys.append(flat)
        out[ch] = (ttf.advance(gid), polys)
    return ttf.upm, out, missing


def main():
    result = {"UPM": None, "FONTS": {}}
    for name, path in FONTS.items():
        upm, glyphs, missing = extract(path)
        result["UPM"] = upm
        result["FONTS"][name] = glyphs
        print(f"{name}: {len(glyphs)} glyphs, upm={upm}, missing={missing!r}")
    with open("font_data.py", "w") as f:
        f.write("# Vector font subset extracted from Liberation Sans (SIL OFL 1.1)\n")
        f.write("# by font_extract.py from the system fonts. Quadratic outlines\n")
        f.write("# flattened to polygons in font units (y up). Stdlib-only use.\n")
        f.write("UPM = %d\n" % result["UPM"])
        f.write("FONTS = ")
        f.write(repr(result["FONTS"]))
        f.write("\n")
    print("wrote font_data.py")


if __name__ == "__main__":
    main()
