from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
    QAbstractItemView,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QIcon


class TeamExplorerWidget(QWidget):
    # Define custom signals
    team_delete = Signal(int)  # Emitted when delete is selected from context menu
    team_open = Signal(int)  # Emitted when item is clicked or opened from menu

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create list widget
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.setSpacing(10)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)

        # Enable selection
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        # Connect signals
        self.list_widget.itemClicked.connect(self._handle_item_click)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.list_widget)

    def add_team(self, name: str, icon: QIcon, team_number: int):
        """Add a new team to the widget."""
        item = QListWidgetItem(icon, name)
        item.setData(
            Qt.ItemDataRole.UserRole, team_number
        )  # Store team number in item data
        self.list_widget.addItem(item)

    def clear_teams(self):
        """Remove all teams from the widget."""
        self.list_widget.clear()

    def _handle_item_click(self, item: QListWidgetItem):
        """Handle left-click on item."""
        team_number = item.data(Qt.ItemDataRole.UserRole)
        self.team_open.emit(team_number)

    def _show_context_menu(self, position):
        """Show context menu for right-clicked item."""
        item = self.list_widget.itemAt(position)
        if not item:
            return

        team_number = item.data(Qt.ItemDataRole.UserRole)

        # Create context menu
        context_menu = QMenu(self)

        # Add menu actions
        open_action = context_menu.addAction("Open")
        delete_action = context_menu.addAction("Delete ALL team pictures")

        # Show menu and handle selection
        action = context_menu.exec_(self.list_widget.mapToGlobal(position))

        if action == open_action:
            self.team_open.emit(team_number)
        elif action == delete_action:
            self.team_delete.emit(team_number)

    def clear(self):
        """Remove all teams from the widget."""
        self.list_widget.clear()

    def get_selected_team(self) -> int:
        """Return the team number of the selected item."""
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return 0
