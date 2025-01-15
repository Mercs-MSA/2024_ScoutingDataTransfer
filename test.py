# Import necessary PyQt5 modules
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
    QVBoxLayout,
    QStackedWidget,
    QLabel,
    QPushButton,
)
import sys
from PySide6.QtGui import QIcon
from PySide6 import QtGui


# Create a custom QWidget subclass for the stacked widget
class StackedWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Set up initial properties of the widget
        self.title = "PyQt5 StackedWidget"
        self.top = 200
        self.left = 500
        self.width = 300
        self.height = 200
        self.setWindowIcon(QtGui.QIcon("icon.png"))  # Set window icon
        self.setWindowTitle(self.title)  # Set window title
        self.setGeometry(
            self.left, self.top, self.width, self.height
        )  # Set window geometry

        # Call method to create stacked widget and display it
        self.stackedWidget()
        self.show()

    # Method to create and configure the QStackedWidget
    def stackedWidget(self):
        # Create a QVBoxLayout to arrange widgets vertically
        vbox = QVBoxLayout()

        # Create the QStackedWidget
        self.stackedWidget = QStackedWidget()
        vbox.addWidget(self.stackedWidget)  # Add the stacked widget to the layout

        # Loop to create and add labels and buttons to the stacked widget
        for x in range(0, 8):
            label = QLabel("Stacked Child: " + str(x))
            label.setFont(QtGui.QFont("sanserif", 15))
            label.setStyleSheet("color:red")
            self.stackedWidget.addWidget(label)  # Add label to the stacked widget

            self.button = QPushButton("Stack" + str(x))
            self.button.setStyleSheet("background-color:green")
            self.button.page = x
            self.button.clicked.connect(self.btn_clicked)  # Connect button click event
            vbox.addWidget(self.button)  # Add button to the layout

        # Set the layout of the widget
        self.setLayout(vbox)

    # Method to handle button click events
    def btn_clicked(self):
        self.button = self.sender()  # Get the button that triggered the event
        self.stackedWidget.setCurrentIndex(
            self.button.page - 1
        )  # Set current index of the stacked widget


# Create QApplication instance and main window
App = QApplication(sys.argv)
window = StackedWidget()

# Execute the application
sys.exit(App.exec_())
