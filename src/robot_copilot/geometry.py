from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Polygon

from robot_copilot.site import Site


@dataclass(frozen=True)
class SiteGeometry:
    fence_inset: Polygon
    keep_outs: tuple[tuple[str, Polygon], ...]

    @classmethod
    def build(cls, site: Site) -> SiteGeometry:
        fence = Polygon(site.geofence)
        inset = fence.buffer(-site.geofence_margin_m)
        if inset.is_empty or inset.geom_type != "Polygon":
            raise ValueError("invalid fence inset")
        keep_outs = tuple(
            (ko.name, Polygon(ko.polygon).buffer(ko.margin_m)) for ko in site.keep_out
        )
        return cls(fence_inset=inset, keep_outs=keep_outs)
