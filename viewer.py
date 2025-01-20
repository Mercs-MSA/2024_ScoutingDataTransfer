import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QTransform,
    QBrush,
    QPen,
    QColor,
    QWheelEvent,
)
from PySide6.QtCore import Qt, QRectF, QPointF

import constants


class NavigatorRect(QGraphicsRectItem):
    def __init__(self, x, y, width, height, outer_rect, parent=None):
        super().__init__(x, y, width, height, parent)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setPen(QPen(QColor(255, 255, 255)))
        self.setBrush(QBrush(QColor(255, 255, 255, 50)))
        self.setAcceptHoverEvents(True)
        self.outer_rect = outer_rect

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # Get the outer rectangle's position and dimensions
        outer_pos = self.outer_rect.pos()
        outer_rect = self.outer_rect.rect()
        my_rect = self.rect()
        my_pos = self.pos()

        # Calculate bounds relative to scene coordinates
        min_x = outer_pos.x()
        max_x = outer_pos.x() + outer_rect.width() - my_rect.width()
        min_y = outer_pos.y()
        max_y = outer_pos.y() + outer_rect.height() - my_rect.height()

        # Constrain position
        new_x = max(min_x, min(max_x, my_pos.x()))
        new_y = max(min_y, min(max_y, my_pos.y()))

        self.setPos(new_x, new_y)

        # Update main view
        if isinstance(self.scene(), ImageViewerScene):
            self.scene().viewer.update_view_from_navigator()

    def update_dimensions(self, width, height):
        self.setRect(0, 0, width, height)


class ImageViewerScene(QGraphicsScene):
    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer


class ImageViewer(QWidget):
    def __init__(self, image: QPixmap, team: int):
        super().__init__()
        self.image = image
        self.team = team
        self.zoom_factor = constants.IMAGE_VIEWER_DEFAULT_ZOOM
        self.initUI()

    def initUI(self):
        # Main layout
        layout = QVBoxLayout()

        # Top bar with team number
        top_bar = QHBoxLayout()
        team_label = QLabel(f"Team Number: {self.team}")
        team_label.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(team_label)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(lambda: self.zoom(1.2))
        top_bar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(lambda: self.zoom(0.8))
        top_bar.addWidget(zoom_out_btn)

        reset_zoom_btn = QPushButton("Reset Zoom")
        reset_zoom_btn.clicked.connect(self.reset_zoom)
        top_bar.addWidget(reset_zoom_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_image)
        top_bar.addWidget(save_btn)

        # Create stack layout for main view and navigator
        self.main_container = QWidget()
        self.main_container.setLayout(QHBoxLayout())
        self.main_container.layout().setContentsMargins(0, 0, 0, 0)

        # Main graphics view
        self.view = QGraphicsView()
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setInteractive(False)

        def view_event_filter(event: QWheelEvent):
            event.ignore()

        self.view.wheelEvent = view_event_filter

        self.scene = ImageViewerScene(self)
        self.view.setScene(self.scene)
        self.view.setRenderHint(
            self.view.renderHints() | QPainter.RenderHint.SmoothPixmapTransform
        )

        # Add image to main scene
        self.pixmap_item = self.scene.addPixmap(self.image)
        self.main_container.layout().addWidget(self.view)

        # Navigator view (overlay)
        self.nav_view = QGraphicsView()
        self.nav_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.nav_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_scene = ImageViewerScene(self)
        self.nav_view.setScene(self.nav_scene)

        # Make navigator background transparent
        self.nav_view.setStyleSheet("background: transparent;")
        self.nav_view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Add navigator outline rectangle (black with 50% opacity)
        self.nav_outline = QGraphicsRectItem()
        self.nav_outline.setPen(QPen(Qt.PenStyle.NoPen))
        self.nav_outline.setBrush(QBrush(QColor(0, 0, 0, 127)))
        self.nav_scene.addItem(self.nav_outline)

        # Add viewport rectangle
        self.nav_rect = NavigatorRect(0, 0, 0, 0, self.nav_outline)
        self.nav_scene.addItem(self.nav_rect)

        # Set navigator position
        self.nav_view.setParent(self.main_container)

        layout.addWidget(self.main_container)
        self.setLayout(layout)

        self.reset_zoom()

    def resizeEvent(self, event):
        if event:
            super().resizeEvent(event)

        # Update main view scaling
        if self.image and not self.image.isNull():
            view_rect = self.view.rect()
            scene_rect = QRectF(self.pixmap_item.boundingRect())

            # Calculate scale factors
            scale_x = view_rect.width() / scene_rect.width()
            scale_y = view_rect.height() / scene_rect.height()
            scale = min(scale_x, scale_y)

            # Apply transform
            transform = QTransform()
            transform.scale(scale * self.zoom_factor, scale * self.zoom_factor)
            self.view.setTransform(transform)

            # Update navigator size and position
            self.update_navigator_size()
            self.update_navigator()

    def update_navigator_size(self):
        # Calculate new navigator size based on view size
        view_rect = self.view.rect()
        nav_width = int(view_rect.width() * constants.IMAGE_VIEWER_NAVIGATOR_SCALE)
        nav_height = int(view_rect.height() * constants.IMAGE_VIEWER_NAVIGATOR_SCALE)

        # Update navigator view size
        self.nav_view.setFixedSize(nav_width, nav_height)

        # Update scene rect
        self.nav_scene.setSceneRect(0, 0, nav_width, nav_height)

        # Update outline rectangle
        self.nav_outline.setRect(0, 0, nav_width, nav_height)

    def update_navigator(self):
        # Update navigator rectangle size and visibility
        if self.zoom_factor <= 1.0:
            self.nav_view.hide()
            return
        else:
            self.nav_view.show()

        view_rect = self.view.viewport().rect()

        # Calculate the scale between navigator and main view
        nav_width = self.nav_view.width()
        nav_height = self.nav_view.height()
        nav_scale_x = nav_width / self.image.width()
        nav_scale_y = nav_height / self.image.height()

        # Update navigator rectangle size and position
        nav_rect_width = view_rect.width() * nav_scale_x / self.zoom_factor
        nav_rect_height = view_rect.height() * nav_scale_y / self.zoom_factor

        self.nav_rect.setRect(0, 0, nav_rect_width, nav_rect_height)

        # Update position based on view center
        center = self.view.mapToScene(view_rect.center())
        nav_x = (center.x() * nav_scale_x) - (nav_rect_width / 2)
        nav_y = (center.y() * nav_scale_y) - (nav_rect_height / 2)

        self.nav_rect.setPos(nav_x, nav_y)

    def update_view_from_navigator(self):
        if self.zoom_factor <= 1.0:
            return

        # Get navigator rectangle position
        nav_pos = self.nav_rect.pos()

        # Calculate scale factors
        nav_scale_x = self.nav_view.width() / self.view.width()
        nav_scale_y = self.nav_view.height() / self.view.height()

        # Calculate scene position
        scene_x = nav_pos.x() / nav_scale_x
        scene_y = nav_pos.y() / nav_scale_y

        # Center the view on this position
        self.view.centerOn(
            QPointF(
                scene_x + (self.view.viewport().width() / (2 * self.zoom_factor)),
                scene_y + (self.view.viewport().height() / (2 * self.zoom_factor)),
            )
        )

    def zoom(self, factor):
        self.zoom_factor = min(
            max(self.zoom_factor * factor, constants.IMAGE_VIEWER_ZOOM_RANGE[0]),
            constants.IMAGE_VIEWER_ZOOM_RANGE[1],
        )
        self.resizeEvent(None)

    def reset_zoom(self):
        self.zoom_factor = constants.IMAGE_VIEWER_DEFAULT_ZOOM
        self.resizeEvent(None)

    def save_image(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "", "Images (*.png *.jpg *.bmp)"
        )
        if file_name:
            self.image.save(file_name)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Load a sample image (replace with your image path)
    try:
        pixmap = QPixmap("icons/generic_robot.png")
        if pixmap.isNull():
            raise FileNotFoundError(
                "Image not found. Please place image.png in the same directory."
            )
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    viewer = ImageViewer(pixmap, 1234)
    viewer.show()
    sys.exit(app.exec())
