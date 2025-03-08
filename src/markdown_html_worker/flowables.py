from reportlab.lib import colors
from reportlab.platypus import Flowable

class VerticalSpace(Flowable):
    """Flowable that adds vertical space."""
    def __init__(self, space):
        self.space = space
    def wrap(self, *args):
        return (0, self.space)
    def draw(self):
        pass

class DottedLineFlowable(Flowable):
    """Draws a dotted (dashed) horizontal line across the given width."""
    def __init__(self, width, line_width=1, dash=(1,2), color=colors.black):
        super().__init__()
        self.width = width
        self.line_width = line_width
        self.dash = dash
        self.color = color
    def wrap(self, available_width, available_height):
        return (self.width, self.line_width)
    def draw(self):
        self.canv.saveState()
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.line_width)
        self.canv.setDash(self.dash)
        self.canv.line(0, 0, self.width, 0)
        self.canv.restoreState()

class SolidLineFlowable(DottedLineFlowable):
    """Draws a solid horizontal line across the given width."""
    def __init__(self, width, line_width=1, color=colors.black):
        # Use empty tuple instead of None for dash pattern
        super().__init__(width, line_width=line_width, dash=(), color=color)