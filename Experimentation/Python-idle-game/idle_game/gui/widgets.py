from PySide6.QtWidgets import QProgressBar, QStylePainter, QStyleOptionProgressBar
from PySide6.QtCore import Qt, QPropertyAnimation, Property, QRect
from PySide6.QtGui import QPainter, QLinearGradient, QColor

import random

class PulseProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Use a range that includes a long "idle" period off-screen
        # -1.0 to 3.0 means it spends 1/4 of time pulsing and much time waiting
        self._pulse_offset = random.uniform(-1.0, 3.0) 
        self._pulse_direction = "ltr" # "ltr" or "rtl"
        
        self.animation = QPropertyAnimation(self, b"pulse_offset")
        self.animation.setDuration(random.randint(6000, 10000)) # Randomize speed (6-10s)
        self.animation.setStartValue(-1.5) # Off-screen left
        self.animation.setEndValue(3.5)   # Off-screen right
        self.animation.setLoopCount(-1)
        
        # Random start position
        self.animation.setCurrentTime(random.randint(0, 6000))
        self.animation.start()

    @Property(float)
    def pulse_offset(self):
        return self._pulse_offset

    @pulse_offset.setter
    def pulse_offset(self, value):
        self._pulse_offset = value
        self.update()

    def setPulseDirection(self, direction):
        self._pulse_direction = direction
        if direction == "rtl":
            self.animation.setStartValue(1.5)
            self.animation.setEndValue(-0.5)
        else:
            self.animation.setStartValue(-0.5)
            self.animation.setEndValue(1.5)

    def paintEvent(self, event):
        # Let the standard style draw the background and chunk first
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # Calculate the chunk area
        val_range = self.maximum() - self.minimum()
        if val_range <= 0: return
        
        progress = (self.value() - self.minimum()) / val_range
        chunk_width = width * progress
        
        # Determine the actual chunk rectangle (handling inverted appearance)
        if self.invertedAppearance():
            chunk_rect = QRect(width - chunk_width, 0, chunk_width, height)
        else:
            chunk_rect = QRect(0, 0, chunk_width, height)
            
        # Clip to the chunk area
        painter.setClipRect(chunk_rect)
        
        # Adjust shimmer position relative to the WHOLE width for smooth panning
        shimmer_width = width * 0.4
        pos = width * self._pulse_offset
        
        gradient = QLinearGradient()
        if self._pulse_direction == "ltr":
            gradient.setStart(pos - shimmer_width/2, 0)
            gradient.setFinalStop(pos + shimmer_width/2, 0)
        else:
            gradient.setStart(pos + shimmer_width/2, 0)
            gradient.setFinalStop(pos - shimmer_width/2, 0)
            
        # Light elegant pulse
        highlight = QColor(255, 255, 255, 0)
        mid_shine = QColor(255, 255, 255, 60) # Slightly stronger shine now that it's clipped
        
        gradient.setColorAt(0, highlight)
        gradient.setColorAt(0.5, mid_shine)
        gradient.setColorAt(1, highlight)
        
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        
        # Draw shimmer over the WHOLE area (the clip will restrict it to the chunk)
        shimmer_rect = QRect(2, 2, rect.width()-4, rect.height()-4)
        painter.drawRoundedRect(shimmer_rect, 5, 5)
        
        painter.end()
