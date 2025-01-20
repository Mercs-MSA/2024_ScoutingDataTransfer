from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QToolButton,
    QLabel,
    QTextBrowser,
    QStackedWidget,
    QWidget,
)
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QPixmap, QFont, QMouseEvent

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

        self.team_number = QLabel("Team 0000")
        self.team_number.setFont(
            QFont(self.team_number.font().family(), 22, QFont.Weight.Bold)
        )
        self.dataview_layout.addWidget(self.team_number)

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
        self.team_number.setText(f"Team {team_number}")

    def set_html(self, html: str):
        if isinstance(self.html, QTextBrowser):
            self.html.setText(html)
        else:
            self.html.setHtml(html)

    def open_image_viewer(self, event: QMouseEvent):
        if self.image_viewer:
            self.image_viewer.close()
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
