from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QPushButton, QScrollArea

from functools import partial

class CarouselWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.currentIndex = -1

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        self.inner_widget = QWidget(self.scroll_area)
        self.layout = QHBoxLayout(self.inner_widget)
        self.inner_widget.setLayout(self.layout)

        self.scroll_area.setWidget(self.inner_widget)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.scroll_area)

        self.widgets = []

    def add_widget(self, widget, data):
        for w in self.widgets:
            if w["data"] == data:
                return

        self.widgets.append({"w": widget, "data": data})
        widget.mousePressEvent = partial(lambda _: self._widget_activation(widget, len(self.widgets) - 1))
        self.layout.addWidget(widget)

    def remove_widget(self, data):
        for item in self.widgets:
            if item["data"] == data:
                self.layout.removeWidget(item["w"])
                item["w"].setParent(None)

    def clear_widgets(self):
        for i in reversed(range(self.layout.count())):
            w = self.layout.itemAt(i).widget()
            w.deleteLater()

        self.widgets = []

    def setCurrentIndex(self, idx: int):
        for widget in self.widgets:
            widget["w"].setSelected(False)

        self.widgets[idx]["w"].setSelected(True)

    def _widget_activation(self, widget, idx):
        for w in self.widgets:
            w["w"].setSelected(False)
        widget.setSelected(True)

        self.currentIndex = idx


if __name__ == '__main__':
    app = QApplication([])
    carousel = CarouselWidget()

    # Example: Adding widgets
    carousel.add_widget(QPushButton("A"), "a")
    carousel.add_widget(QPushButton("B"), "b")
    carousel.add_widget(QPushButton("C"), "c")
    carousel.remove_widget("c")

    carousel.show()
    app.exec()
