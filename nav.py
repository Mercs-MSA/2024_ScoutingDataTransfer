import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolButton,
    QLabel,
    QPushButton,
    QFrame,
    QGraphicsOpacityEffect,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Property, Signal
from typing import List, Tuple, Optional


class AnimatedNavButton(QFrame):
    clicked = Signal()
    
    def __init__(self, text: str, icon, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._text = text
        self._icon = icon
        self._text_opacity = 1.0
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.button = QToolButton()
        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.button.setCheckable(True)
        self.button.setIconSize(QSize(24, 24))
        self.button.setIcon(icon)
        self.button.clicked.connect(self.clicked.emit)
        self.setMinimumHeight(40)

        self.text = QLabel(text)
        layout.addWidget(self.text)

        self.text_opacity_effect = QGraphicsOpacityEffect(self.text)
        self.text_opacity_effect.setOpacity(1)
        self.text.setGraphicsEffect(self.text_opacity_effect)

        self.text_animation = None
        self.text_slide_animation = None

    def get_text_opacity(self):
        return self._text_opacity
        
    def set_text_opacity(self, opacity):
        self._text_opacity = opacity
        self.text_opacity_effect.setOpacity(opacity)

    def set_text_shown(self, show: bool):
        self.text_animation = QPropertyAnimation(self, b"text_opacity")
        self.text_animation.setStartValue(0 if show else 1)
        self.text_animation.setEndValue(1 if show else 0)
        self.text_animation.setDuration(300)
        self.text_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.text_animation.finished.connect(lambda: self.text.setVisible(False) if not show else None)
        if show:
            self.text.setVisible(True)
        self.text_animation.start()

        self.text_slide_animation = QPropertyAnimation(self, b"text_width")
        self.text_slide_animation.setStartValue(0 if show else self.text.sizeHint().width())
        self.text_slide_animation.setEndValue(self.text.sizeHint().width() if show else 0)
        self.text_slide_animation.setDuration(300)
        self.text_slide_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.text_slide_animation.currentLoopChanged.connect(self.update)
        self.text_slide_animation.start()

    text_opacity = Property(float, get_text_opacity, set_text_opacity, None, "text_opacity")
    text_width = Property(int, lambda self: self.text.width, lambda self, value: self.text.setFixedWidth(value), None, "text_width")

    def sizeHint(self):
        return self.button.sizeHint() + QSize(self.text.width() + 2, 0) if self.text.isVisible() else QSize(2, 0)


class SideNavigationBar(QWidget):
    """A vertical navigation bar with animated icon buttons."""
    
    currentChanged = Signal(int)  # Signal emitted when the current index changes
    
    def __init__(self, items: List[Tuple[str, str]], parent: Optional[QWidget] = None):
        """
        Initialize the navigation bar with a list of items.
        
        Args:
            items: List of tuples containing (text, icon_name) pairs
                  icon_name should be a Font Awesome name (e.g., "fa.home")
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(20)
        
        # Create navigation buttons
        self._nav_buttons: List[AnimatedNavButton] = []
        self._current_index = -1
        self._show_text = True

        self.toggle_button = QPushButton()
        self.toggle_button.setIcon(qta.icon("mdi6.menu"))
        self.toggle_button.setIconSize(QSize(24, 24))
        self.toggle_button.clicked.connect(self.toggle_text_visibility)
        self._layout.addWidget(self.toggle_button)
        
        self._layout.addStretch()

        # Add buttons for each item
        for text, icon_name in items:
            icon = qta.icon(icon_name)
            self._add_button(text, icon)
            
        self._layout.addStretch()

        self._layout.addSpacing(self.toggle_button.sizeHint().height())
        
        # Set initial selection if we have buttons
        if self._nav_buttons:
            self.setCurrentIndex(0)
            
    def _add_button(self, text: str, icon):
        """Add a new navigation button."""
        button = AnimatedNavButton(text, icon)
        button.button.setAutoExclusive(True)
        button.clicked.connect(lambda: self.setCurrentIndex(len(self._nav_buttons)))
        self._layout.addWidget(button)
        self._nav_buttons.append(button)
        
    def setCurrentIndex(self, index: int):
        """Set the current selected index."""
        if 0 <= index < len(self._nav_buttons) and index != self._current_index:
            self._current_index = index
            
            # Update button states
            for i, button in enumerate(self._nav_buttons):
                button.button.setChecked(i == index)
                
            self.currentChanged.emit(index)

        for i, button in enumerate(self._nav_buttons):
            button.button.setChecked(i == index)
            
    def currentIndex(self) -> int:
        """Get the current selected index."""
        return self._current_index
    
    def count(self) -> int:
        """Get the number of navigation items."""
        return len(self._nav_buttons)
    
    def toggle_text_visibility(self):
        """Toggle the visibility of button text."""
        self._show_text = not self._show_text
        for button in self._nav_buttons:
            button.set_text_shown(self._show_text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Side Navigation Demo")
        self.resize(800, 600)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create navigation items
        nav_items = [
            ("Home", "fa.home"),
            ("Profile", "fa.user"),
            ("Settings", "fa.cog"),
            ("Info", "fa.info-circle"),
        ]
        
        # Create SideNavigationBar
        self.nav_bar = SideNavigationBar(nav_items)
        main_layout.addWidget(self.nav_bar)
        
        # Demo content area
        content = QWidget()
        content.setStyleSheet("background-color: #f0f0f0;")
        main_layout.addWidget(content, stretch=1)
        
        # Connect to navigation changes
        self.nav_bar.currentChanged.connect(self._on_nav_changed)
        
    def _on_nav_changed(self, index: int):
        print(f"Navigation changed to index {index}")


if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())