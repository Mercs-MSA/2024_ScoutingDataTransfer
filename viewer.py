import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QScroller,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QTransform,
)
from PySide6.QtCore import QRectF

import constants


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

        self.scene = ImageViewerScene(self)
        self.view.setScene(self.scene)
        self.view.setRenderHint(
            self.view.renderHints() | QPainter.RenderHint.SmoothPixmapTransform
        )

        QScroller.grabGesture(
            self.view.viewport(), QScroller.ScrollerGestureType.TouchGesture
        )

        # Add image to main scene
        self.pixmap_item = self.scene.addPixmap(self.image)
        self.main_container.layout().addWidget(self.view)

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
