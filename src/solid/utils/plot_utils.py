"""
Plot utilities — Korean font setup for matplotlib.

Usage
-----
    from solid.utils import setup_korean_font
    setup_korean_font()          # call once before any plt code

Or in scripts (no package import):
    import sys; sys.path.insert(0, 'src')
    from solid.utils import setup_korean_font; setup_korean_font()
"""

import matplotlib.pyplot as plt


def setup_korean_font(font: str = "Malgun Gothic") -> None:
    """Set matplotlib rcParams for Korean text rendering.

    Parameters
    ----------
    font : str
        Font name to use. Defaults to 'Malgun Gothic' (bundled on Windows).
        Fallback order: Malgun Gothic → NanumGothic → AppleGothic → sans-serif
    """
    plt.rcParams.update({
        "font.family": font,
        "axes.unicode_minus": False,   # prevent minus sign from rendering as box
    })
