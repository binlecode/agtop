from dashing.dashing import HGauge, VGauge, HChart, hbar_elements, vbar_elements

from .color_modes import value_to_rgb


class _GradientRendererMixin:
    def _color_seq(self, term, percent):
        pct = max(0.0, min(100.0, float(percent)))
        cache = getattr(self, "_gradient_cache", None)
        if cache is None:
            cache = {}
            self._gradient_cache = cache

        seq = cache.get(pct)
        if seq is None:
            r, g, b = value_to_rgb(pct)
            seq = str(term.color_rgb(r, g, b))
            cache[pct] = seq
        return seq

    def _render_cells(self, term, cells):
        # cells: list[(char, percent_or_none)]
        parts = []
        active_seq = None
        for char, pct in cells:
            if pct is None:
                if active_seq is not None:
                    parts.append(term.normal)
                    active_seq = None
                parts.append(char)
                continue

            seq = self._color_seq(term, pct)
            if seq != active_seq:
                parts.append(seq)
                active_seq = seq
            parts.append(char)

        if active_seq is not None:
            parts.append(term.normal)

        return "".join(parts)


class GradientHGauge(_GradientRendererMixin, HGauge):
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)

        if self.label:
            bar_width = max(0, tbox.w - len(self.label) - 1)
            wi = bar_width * self.value / 100.0
            v_center = int((tbox.h) * 0.5)
        else:
            bar_width = max(0, tbox.w)
            wi = bar_width * self.value / 100.0
            v_center = None

        filled_cells = int(wi)
        partial_index = int((wi - filled_cells) * 7)

        cells = []
        for col in range(bar_width):
            if col < filled_cells:
                pct = (col / max(1, bar_width - 1)) * 100
                cells.append((hbar_elements[-1], pct))
            elif col == filled_cells and partial_index > 0 and filled_cells < bar_width:
                pct = (col / max(1, bar_width - 1)) * 100
                cells.append((hbar_elements[partial_index], pct))
            else:
                cells.append((hbar_elements[0], None))

        bar = self._render_cells(tbox.t, cells)
        for dx in range(0, tbox.h):
            m = tbox.t.move(tbox.x + dx, tbox.y)
            if self.label:
                if dx == v_center:
                    print(m + self.label + " " + bar)
                else:
                    print(m + " " * len(self.label) + " " + bar)
            else:
                print(m + bar)


class GradientVGauge(_GradientRendererMixin, VGauge):
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)
        nh = tbox.h * (self.value / 100.5)

        for dx in range(tbox.h):
            m = tbox.t.move(tbox.x + tbox.h - dx - 1, tbox.y)
            if dx < int(nh):
                char = vbar_elements[-1]
                pct = (dx / max(1, tbox.h - 1)) * 100
                cells = [(char, pct)] * tbox.w
            elif dx == int(nh):
                index = int((nh - int(nh)) * 8)
                if index > 0:
                    char = vbar_elements[index]
                    pct = (dx / max(1, tbox.h - 1)) * 100
                    cells = [(char, pct)] * tbox.w
                else:
                    cells = [(" ", None)] * tbox.w
            else:
                cells = [(" ", None)] * tbox.w

            print(m + self._render_cells(tbox.t, cells))


class GradientHChart(_GradientRendererMixin, HChart):
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)

        for dx in range(tbox.h):
            cells = []
            for dy in range(tbox.w):
                dp_index = -tbox.w + dy
                try:
                    dp = self.datapoints[dp_index]
                    q = (1 - dp / 100) * tbox.h
                    if dx == int(q):
                        index = int((int(q) - q) * 8 - 1)
                        cells.append((vbar_elements[index], dp))
                    elif dx < int(q):
                        cells.append((" ", None))
                    else:
                        cells.append((vbar_elements[-1], dp))
                except IndexError:
                    cells.append((" ", None))

            print(tbox.t.move(tbox.x + dx, tbox.y) + self._render_cells(tbox.t, cells))
