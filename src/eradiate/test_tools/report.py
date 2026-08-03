"""
Test report logging.

This module provides an abstraction layer that routes logging messages to
reporting infrastructure if available, and falls back to standard logging
otherwise.

The current reporting backend is Robot Framework. These components make it
possible to change it in the future.
"""

from __future__ import annotations

import importlib.util
import logging
from io import StringIO
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import matplotlib.pyplot as plt

_logger = logging.getLogger(__name__)


def figure_to_html(fig: plt.Figure) -> str:
    """
    Render a figure in HTML format

    Returns a string containing the rendered HTML. The root tag is a <svg> one.

    Parameters
    ----------
    fig : plt.Figure
        Matplotlib figure to render in HTML.

    Returns
    -------
    str
        Rendered HTML <svg> tag with styling.
    """

    str_i = StringIO()
    fig.savefig(str_i, format="svg", transparent=True, bbox_inches="tight")
    svg = str_i.getvalue()

    # Drop the XML prolog and DOCTYPE: this is embedded in an HTML report. The
    # root <svg> tag carries the figure's own size, so no wrapper is needed.
    svg = svg[svg.index("<svg") :]
    root_end = svg.index(">") + 1

    # Include some CSS in the SVG to render nicely in the test report's dark
    # and light modes. Scoped to paths carrying no inline style, i.e. the glyph
    # definitions of text elements: everything Matplotlib colours itself (data
    # lines, legend swatches, spines, ticks) has a style attribute and must keep
    # its colour, or a colour-mapped chart would be flattened to a single hue.
    style = "<style>path:not([style]) { fill: var(--text-color); }</style>"

    return svg[:root_end] + style + svg[root_end:]


class ReportLogger:
    """
    Send messages and HTML fragments to the active test report.

    Parameters
    ----------
    use_robot : bool, optional
        If ``True``, forward messages to the Robot Framework logger; if
        ``False``, fall back to standard :mod:`logging`. If unset, the Robot
        Framework backend is selected iff the :mod:`robot` package is
        importable.

    Notes
    -----
    The Robot Framework logger is safe to call outside of a Robot run (messages
    are then simply not recorded), so backend selection only depends on package
    availability, not on whether report generation is active.
    """

    def __init__(self, use_robot: bool | None = None):
        if use_robot is None:
            use_robot = importlib.util.find_spec("robot") is not None

        # Any object with a robot.api.logger-compatible info() method works
        self._robot: Any = None

        if use_robot:
            from robot.api import logger as robot_logger

            self._robot = robot_logger

    @property
    def reporting(self) -> bool:
        """
        ``True`` if a report backend is active, i.e. if HTML fragments are
        recorded instead of discarded.
        """
        return self._robot is not None

    def info(self, msg: str) -> None:
        """
        Log an informational message to the test report and the console.

        Parameters
        ----------
        msg : str
            Message to log.
        """
        if self._robot is not None:
            self._robot.info(msg, also_console=True)
        else:
            _logger.info(msg)

    def warning(self, msg: str) -> None:
        """
        Log a warning message to the test report and the console.

        Parameters
        ----------
        msg : str
            Message to log.
        """
        if self._robot is not None:
            self._robot.warn(msg)
        else:
            _logger.warning(msg)

    def html(self, fragment: str) -> None:
        """
        Embed an HTML fragment in the test report.

        Parameters
        ----------
        fragment : str
            HTML fragment to embed (e.g. an ``<svg>`` chart or an xarray HTML
            repr).

        Notes
        -----
        If no report backend is active, the fragment is discarded.
        """
        if self._robot is not None:
            self._robot.info(fragment, html=True, also_console=False)
        else:
            _logger.debug("Discarding HTML report fragment (no report backend)")


#: Default report logger instance, used when no specific instance is injected.
report_logger = ReportLogger()
