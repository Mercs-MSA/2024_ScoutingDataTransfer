from loguru import logger
from PySide6.QtWidgets import (
    QWizard,
    QWizardPage,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QFileDialog,
    QListWidgetItem,
    QPushButton,
)
from PySide6.QtCore import Qt, QSize, QPoint, QItemSelection, QMimeData
from PySide6.QtGui import (
    QLinearGradient,
    QPixmap,
    QColor,
    QPainter,
    QResizeEvent,
    QMouseEvent,
    QImage,
    QDragEnterEvent,
    QDropEvent,
    QValidator,
)
from pillow_heif import register_heif_opener
from PIL import Image
import io
import os
import qtawesome as qta

# Register HEIF opener with Pillow
register_heif_opener()


class DragDropLabel(QLabel):
    """Custom QLabel that supports drag and drop for image files"""

    def __init__(self, parent: "NewPicturesTeamWizard.Page2 | None" = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 2px dashed #1F1F22; min-height: 50px;")
        self.setAcceptDrops(True)
        self.setText("Drop files here to add images\n(or click to pick files)")

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data: QMimeData = event.mimeData()

        # Check if the drag contains URLs (files)
        if mime_data.hasUrls():
            # Check if all URLs are valid image files
            valid_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".heic")
            if all(
                url.toLocalFile().lower().endswith(valid_extensions)
                for url in mime_data.urls()
            ):
                event.acceptProposedAction()
                self.setStyleSheet("border: 2px dashed green; min-height: 50px;")
                return

        event.ignore()
        self.setStyleSheet("border: 2px dashed red; min-height: 50px;")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("border: 2px dashed #1F1F22; min-height: 50px;")

    def dropEvent(self, event: QDropEvent):
        mime_data: QMimeData = event.mimeData()

        if mime_data.hasUrls():
            event.acceptProposedAction()
            file_list = self.parent().file_list  # type: ignore

            # Process each dropped file
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                if file_list.count() < 5 and os.path.isfile(file_path):
                    file_list.addItem(QListWidgetItem(file_path))

            # Update status label
            self.parent().statusLabel.setText(f"{file_list.count()}/5 images uploaded")  # type: ignore

        self.setStyleSheet("border: 2px dashed #1F1F22; min-height: 50px;")


class TeamNumberValidator(QValidator):
    def __init__(self, invalid_teams: list[int]):
        super().__init__()
        self.invalid_teams = invalid_teams

    def validate(self, arg__1, arg__2):
        if (
            (arg__1 in [str(x) for x in self.invalid_teams])
            or not arg__1.isnumeric()
            or len(arg__1) > 5
        ):
            return QValidator.State.Intermediate
        else:
            return QValidator.State.Acceptable


class NewPicturesTeamWizard(QWizard):
    class Page1(QWizardPage):
        def __init__(self, existing_teams: list[int] = [], parent=None):
            super().__init__(parent)

            self.setTitle("New Team Wizard")
            self.setSubTitle("This wizard will help you create a new team entry")

            layout = QFormLayout()
            self.setLayout(layout)

            self.team_number = QLineEdit()
            self.team_number.setPlaceholderText("6369")
            self.team_number.textChanged.connect(lambda: self.completeChanged.emit())
            self.team_number.textChanged.connect(self.check_team_number)
            self.team_number.setValidator(TeamNumberValidator(existing_teams))
            layout.addRow(QLabel("Team Number"), self.team_number)

            self.team_valid = QLabel("Team number is valid")
            layout.addRow(self.team_valid)

        def check_team_number(self):
            if (
                self.team_number.validator().validate(self.team_number.text(), 0)
                == QValidator.State.Acceptable
            ):
                self.team_valid.setText("Team number is valid")
                self.team_valid.setStyleSheet("color: green")
            else:
                self.team_valid.setText("Team number is invalid")
                self.team_valid.setStyleSheet("color: red")

        def isComplete(self) -> bool:
            return (
                self.team_number.validator().validate(self.team_number.text(), 0)
                == QValidator.State.Acceptable
            )

    class Page2(QWizardPage):
        def __init__(self, parent=None):
            super().__init__(parent)

            self.setTitle("Upload Images")
            self.setSubTitle("Upload up to 5 images for the team.")

            # Create layout
            layout = QVBoxLayout()

            file_list_layout = QVBoxLayout()
            self.file_list = QListWidget()
            self.file_list.selectionChanged = self.selection_changed
            self.file_list.setMinimumWidth(300)

            bottom_toolbar = QHBoxLayout()
            delete_btn = QPushButton(qta.icon("mdi6.trash-can"), "Delete")
            delete_btn.setIconSize(QSize(28, 28))
            delete_btn.clicked.connect(self.delete_img)
            bottom_toolbar.addWidget(delete_btn)

            file_list_layout.addWidget(self.file_list)
            file_list_layout.addLayout(bottom_toolbar)

            self.preview = QLabel("Image preview will appear here")
            self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview.setStyleSheet(
                "border: 1px solid #1F1F22; min-height: 256px; min-width: 256px; padding: 10px"
            )
            self.preview.setMaximumWidth(280)

            self.dnd_area = DragDropLabel(self)
            self.dnd_area.mousePressEvent = self.browse_files

            main_layout = QHBoxLayout()
            main_layout.addLayout(file_list_layout, 2)
            main_layout.addWidget(self.preview, 1)

            layout.addLayout(main_layout)
            layout.addWidget(self.dnd_area)

            # Status label
            self.statusLabel = QLabel("0/5 images uploaded")
            layout.addWidget(self.statusLabel)

            self.setLayout(layout)

        def delete_img(self):
            for item in self.file_list.selectedItems():
                self.file_list.takeItem(self.file_list.row(item))
            self.statusLabel.setText(f"{self.file_list.count()}/5 images uploaded")
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Image preview will appear here")
            self.selection_changed(QItemSelection(), QItemSelection())

        def selection_changed(
            self, selected: QItemSelection, deselected: QItemSelection
        ):
            if self.file_list.selectedItems():
                file_path = self.file_list.selectedItems()[0].text()
                if file_path.lower().endswith(".heic"):
                    try:
                        heic_image = Image.open(file_path)
                        rgb_image = heic_image.convert("RGB")
                        buffer = io.BytesIO()
                        rgb_image.save(buffer, format="PNG")
                        buffer.seek(0)
                        qimage = QImage.fromData(buffer.getvalue())
                        pixmap = QPixmap.fromImage(qimage)
                    except Exception as e:
                        logger.error(f"Error converting HEIC preview: {e}")
                        return
                else:
                    pixmap = QPixmap(file_path)

                self.preview.setPixmap(
                    pixmap.scaled(
                        256,
                        256,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        def browse_files(self, ev: QMouseEvent):
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select images", "", "Images (*.png *.jpg *.jpeg *.bmp *.heic)"
            )
            for file in files:
                if self.file_list.count() < 5:
                    self.file_list.addItem(QListWidgetItem(file))
            self.statusLabel.setText(f"{self.file_list.count()}/5 images uploaded")

    def __init__(self, existing_teams: list[int] = [], parent=None):
        super().__init__(parent)

        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumWidth(800)

        self.setWindowTitle("New Team Wizard")
        self.setPixmap(QWizard.WizardPixmap.BannerPixmap, self.generate_banner())
        self.setPixmap(
            QWizard.WizardPixmap.LogoPixmap, qta.icon("mdi6.robot").pixmap(64, 64)
        )

        self.setPage(0, self.Page1(existing_teams, self))
        self.setPage(1, self.Page2(self))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.setPixmap(QWizard.WizardPixmap.BannerPixmap, self.generate_banner())

    def generate_banner(self):
        px = QPixmap(QSize(self.width(), 84))
        px.fill(Qt.GlobalColor.transparent)

        g = QLinearGradient(QPoint(0, 0), QPoint(self.width(), 84))
        g.setColorAt(0, QColor("#A91717"))
        g.setColorAt(1, Qt.GlobalColor.transparent)

        painter = QPainter(px)
        painter.fillRect(px.rect(), g)
        painter.end()

        return px

    def get_team_number(self) -> str:
        """Return the team number entered in Page 1"""
        return self.page(0).team_number.text()  # type: ignore

    def get_pixmaps(self, size: QSize | None = None) -> list[QPixmap]:
        """
        Retrieve all images as QPixmaps, converting HEIC files if necessary.

        Args:
            size: Optional QSize to scale the images to. If None, original size is kept.

        Returns:
            List of QPixmaps
        """
        pixmaps = []
        file_list = self.page(1).file_list  # type: ignore

        for i in range(file_list.count()):
            file_path = file_list.item(i).text()

            # Handle HEIC files
            if file_path.lower().endswith(".heic"):
                try:
                    # Open HEIC file with Pillow
                    heic_image = Image.open(file_path)

                    # Convert to RGB (HEIC might be in a different color space)
                    rgb_image = heic_image.convert("RGB")

                    # Convert PIL Image to bytes
                    buffer = io.BytesIO()
                    rgb_image.save(buffer, format="PNG")
                    buffer.seek(0)

                    # Create QImage from bytes
                    image_data = buffer.getvalue()
                    qimage = QImage.fromData(image_data)
                    pixmap = QPixmap.fromImage(qimage)

                except Exception as e:
                    logger.error(f"Error converting HEIC file: {e}")
                    continue
            else:
                # Handle regular image formats
                pixmap = QPixmap(file_path)

            # Scale if size is specified
            if size and not pixmap.isNull():
                pixmap = pixmap.scaled(
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            if not pixmap.isNull():
                pixmaps.append(pixmap)

        return pixmaps
