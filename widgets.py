from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QToolButton,
    QLabel,
    QTextBrowser,
    QStackedWidget,
    QWidget,
    QScrollArea,
)
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QPixmap, QFont, QMouseEvent

from loguru import logger
import qtawesome as qta

import constants
import ssw
import viewer


class Sidebar(QFrame):
    close_action = Signal()
    edit_images_action = Signal(int)

    def __init__(self, parent=None, renderer: int = constants.SIDEBAR_RENDERER):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.Box)

        self.team = 0
        self.pixmaps: list[QPixmap] = []

        self.image_viewer: viewer.ImageViewer | None = None

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.top_layout = QHBoxLayout()
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addLayout(self.top_layout)

        self.top_layout.addStretch()

        self.top_close = QToolButton()
        self.top_close.setIcon(qta.icon("mdi6.close-circle", color="#f44336"))
        self.top_close.setFixedSize(QSize(24, 24))
        self.top_close.clicked.connect(self.close_action.emit)
        self.top_layout.addWidget(self.top_close)

        self.root_widget = QStackedWidget()
        self.root_widget.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addWidget(self.root_widget)

        self.unselected_widget = QWidget()
        self.root_widget.insertWidget(0, self.unselected_widget)

        self.unselected_layout = QVBoxLayout()
        self.unselected_widget.setLayout(self.unselected_layout)

        self.unselected_text = QLabel("Select a datapoint to get started")
        self.unselected_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unselected_layout.addWidget(self.unselected_text)

        self.dataview_widget = QWidget()
        self.root_widget.insertWidget(1, self.dataview_widget)

        self.dataview_layout = QVBoxLayout()
        self.dataview_layout.setContentsMargins(4, 0, 4, 4)
        self.dataview_widget.setLayout(self.dataview_layout)

        self.carousel_layout = QHBoxLayout()
        self.carousel_layout.setContentsMargins(0, 0, 0, 0)
        self.dataview_layout.addLayout(self.carousel_layout)

        self.carousel_back = QToolButton()
        self.carousel_back.setIcon(qta.icon("mdi6.chevron-left"))
        self.carousel_back.setIconSize(QSize(64, 64))
        self.carousel_back.setFixedWidth(32)
        self.carousel_layout.addWidget(self.carousel_back)

        self.carousel = ssw.SlidingStackedWidget()
        self.carousel.setFixedSize(constants.PICTURE_DISPLAY_MAX_RESOLUTION)
        self.carousel.set_direction(Qt.Axis.XAxis)
        self.carousel.mousePressEvent = self.open_image_viewer
        self.carousel_layout.addWidget(self.carousel)

        self.carousel_forward = QToolButton()
        self.carousel_forward.setIcon(qta.icon("mdi6.chevron-right"))
        self.carousel_forward.setIconSize(QSize(64, 64))
        self.carousel_forward.setFixedWidth(32)
        self.carousel_layout.addWidget(self.carousel_forward)

        self.carousel_back.clicked.connect(self.carousel.sldie_in_prev)
        self.carousel_forward.clicked.connect(self.carousel.slide_in_next)

        self.carousel_tools_layout = QHBoxLayout()
        self.carousel_tools_layout.setContentsMargins(0, 0, 0, 0)
        self.carousel_tools_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dataview_layout.addLayout(self.carousel_tools_layout)

        self.carousel_page_number = QLabel("Page 1/1")
        self.carousel_tools_layout.addWidget(self.carousel_page_number)
        self.carousel.currentChanged.connect(
            lambda: self.carousel_page_number.setText(
                f"Page {self.carousel.currentIndex() + 1}/{self.carousel.count()}"
            )
        )

        self.edit_images = QToolButton()
        self.edit_images.setIcon(qta.icon("mdi6.image-edit"))
        self.edit_images.setText("Edit Images")
        self.edit_images.setIconSize(QSize(18, 18))
        self.edit_images.setFixedHeight(24)
        self.edit_images.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.edit_images.clicked.connect(
            lambda: self.edit_images_action.emit(int(self.team))
        )
        self.carousel_tools_layout.addWidget(self.edit_images)

        if renderer == 0:
            self.html = QTextBrowser()
            self.html.setReadOnly(True)
        else:
            self.html = QWebEngineView()
            self.html.page().setBackgroundColor(Qt.GlobalColor.transparent)
            self.html.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.last_scroll = 0

            # Save scroll position before loading new content
            self.html.loadStarted.connect(
                lambda: setattr(
                    self, "last_scroll", self.html.page().scrollPosition().y()
                )
            )

            # Restore scroll position after loading completes
            self.html.loadFinished.connect(
                lambda: self.html.page().runJavaScript(
                    f"window.scrollTo(0, {self.last_scroll});"
                )
            )

            self.html.setHtml(
                "<h1 style='color: white;'>Unknown page loading error</h1>"
            )  # prevent glitching on 1st load
        self.html.setMinimumHeight(200)
        self.dataview_layout.addWidget(self.html, 2)

    def set_selected(self, selected: bool):
        if selected:
            self.root_widget.setCurrentIndex(1)
        else:
            self.root_widget.setCurrentIndex(0)

    def set_pixmaps(self, pixmaps: list[QPixmap]):
        self.pixmaps = pixmaps
        for _ in self.carousel.children():  # type: ignore
            w = self.carousel.widget(0)
            if w:
                self.carousel.removeWidget(w)
                w.setParent(None)

        for i, pixmap in enumerate(pixmaps):
            widget = QLabel()
            widget.setPixmap(
                pixmap.scaled(
                    300,
                    300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.carousel.addWidget(widget)

        self.carousel_page_number.setText(
            f"Page {self.carousel.currentIndex() + 1}/{len(pixmaps)}"
        )

    def set_team_number(self, team_number: str | int):
        self.team = team_number

    def set_html(self, html: str):
        if isinstance(self.html, QTextBrowser):
            self.html.setText(html)
        else:
            self.html.setHtml(html)

    def open_image_viewer(self, event: QMouseEvent):
        if self.image_viewer:
            self.image_viewer.close()

        if len(self.pixmaps) == 0:
            logger.warning("No images to display")
            return

        self.image_viewer = viewer.ImageViewer(
            self.pixmaps[self.carousel.currentIndex()], int(self.team)
        )
        self.image_viewer.show()


class TeamEntryWidget(QFrame):
    """
    A widget that displays a team number and an arrow to the right
    """

    clicked = Signal(str)

    def __init__(self, team_number: str | int, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.Box)

        self.root_layout = QHBoxLayout(self)

        self.team_number = QLabel(str(team_number))
        self.team_number.setFont(
            QFont(self.team_number.font().family(), 12, QFont.Weight.Bold)
        )
        self.root_layout.addWidget(self.team_number)

        self.root_layout.addStretch()

        self.arrow = QLabel()
        self.arrow.setPixmap(qta.icon("mdi6.chevron-right").pixmap(QSize(28, 28)))
        self.root_layout.addWidget(self.arrow)

        self.setFixedHeight(self.sizeHint().height())

    def mousePressEvent(self, event):
        self.clicked.emit(self.team_number.text())
        super().mousePressEvent(event)


class QWidgetList(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWidgetResizable(True)
        self.container = QWidget()
        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setSpacing(5)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.root_layout.addWidget(self.stack)
        self.setWidget(self.container)

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(5)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.list_widget)

        self.loading_widget = QWidget()
        self.loading_layout = QVBoxLayout(self.loading_widget)
        self.loading_label = QLabel("Please Wait...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_spinner = qta.IconWidget()
        self.animation = qta.Spin(self.loading_spinner)
        self.loading_spinner.setIconSize(QSize(128, 128))
        self.loading_spinner.setIcon(qta.icon("msc.loading", animation=self.animation))
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_layout.addWidget(self.loading_spinner)
        self.loading_layout.addWidget(self.loading_label)
        self.loading_widget.setLayout(self.loading_layout)
        self.stack.addWidget(self.loading_widget)

        self.list_layout.addStretch()

    def add_widget(self, widget: QWidget):
        """Add a widget to the list."""
        self.list_layout.insertWidget(self.list_layout.count() - 1, widget)

    def remove_widget(self, widget: QWidget):
        """Remove a specific widget from the list."""
        self.list_layout.removeWidget(widget)
        widget.setParent(None)

    def clear_widgets(self):
        """Remove all widgets from the list."""
        while self.list_layout.count() - 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def set_spacing(self, spacing: int):
        """Set spacing between widgets."""
        self.list_layout.setSpacing(spacing)

    def set_loading(self, loading: bool):
        """Show or hide the loading screen."""
        if loading:
            self.stack.setCurrentWidget(self.loading_widget)
        else:
            self.stack.setCurrentWidget(self.list_widget)


class Chip(QWidget):
    # Small widget that displays a single piece of data
    def __init__(self, label, color: str = "#FFB3A9"):
        super().__init__()
        self.label = label
        self.color = color
        self.initUI()
        self.setFixedWidth(self.sizeHint().width())
        self.setFixedHeight(40)

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel(self.label)
        layout.addWidget(self.label)

        self.label.setStyleSheet("font-weight: bold;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # background color, rounded corners, padding, etc.
        r, g, b = tuple(int(self.color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        self.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, 0.5); border-radius: 11px; padding: 2px;"
        )
