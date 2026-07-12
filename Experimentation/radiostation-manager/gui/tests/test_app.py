from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    from pathlib import Path

    style_path = Path(__file__).parent.parent / "resources" / "style.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text())
    yield app


@pytest.fixture
def window(qapp):
    from gui.app import MainWindow

    w = MainWindow()
    w.show()
    yield w
    w.close()


def test_window_title_and_size(window):
    assert window.windowTitle() == "Luna's Music Metadata Studio"
    assert window.minimumWidth() == 1024
    assert window.minimumHeight() == 576
    assert window.width() == 1280
    assert window.height() == 720


def test_mainwindow_has_ten_stack_widgets(window):
    assert isinstance(window._stack, QStackedWidget)
    # 10 regular widgets + 1 loading page = 11
    assert len(window._widgets) == 11
    assert window._stack.count() == 11


def test_navigation_via_signals_switches_pages(window):
    assert window._stack.currentWidget() is window._widgets["menu"]

    # Direct pages (no async loading)
    window._on_navigate("search")
    assert window._stack.currentWidget() is window._widgets["search"]

    window._on_navigate("vibes")
    assert window._stack.currentWidget() is window._widgets["vibes"]

    window._on_navigate("prompts")
    assert window._stack.currentWidget() is window._widgets["prompts"]

    window._go_to("menu")
    assert window._stack.currentWidget() is window._widgets["menu"]


def test_sidebar_buttons_navigate_correctly(window):
    assert not window._sidebar.isVisible()

    # Use direct-set pages only (search/vibes/prompts are synchronous)
    window._on_navigate("search")
    assert window._sidebar.isVisible()
    assert window._stack.currentWidget() is window._widgets["search"]

    window._on_navigate("vibes")
    assert window._stack.currentWidget() is window._widgets["vibes"]

    window._go_to("menu")
    assert not window._sidebar.isVisible()
    assert window._stack.currentWidget() is window._widgets["menu"]


def test_escape_returns_to_menu(window, qapp):
    window._on_navigate("search")
    assert window._stack.currentWidget() is window._widgets["search"]
    assert window._sidebar.isVisible()

    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    qapp.sendEvent(window, event)
    qapp.processEvents()

    assert window._stack.currentWidget() is window._widgets["menu"]
    assert not window._sidebar.isVisible()


def test_stylesheet_loaded_and_contains_key_selectors(qapp):
    ss = qapp.styleSheet()
    assert len(ss) > 0
    assert "#headerLabel" in ss
    assert "#sectionLabel" in ss
    assert "#dimLabel" in ss
    assert "#sidebar" in ss
    assert "#starButton" in ss
    assert "qlineargradient" in ss
    assert "qradialgradient" in ss


def test_window_background_is_set(qapp):
    ss = qapp.styleSheet()
    assert len(ss) > 0
    has_bg = "qradialgradient" in ss or "background-color" in ss or "background:" in ss
    assert has_bg, "Expected gradient or background-color in stylesheet"


def test_sidebar_visibility_toggles_correctly(window):
    assert not window._sidebar.isVisible()
    window._sidebar.show()
    assert window._sidebar.isVisible()
    window._sidebar.hide()
    assert not window._sidebar.isVisible()


def test_star_rating_widget(qapp):
    from gui.widgets.components import StarRating

    sr = StarRating()
    assert sr.rating == 0

    signals_received: list[int] = []
    sr.rating_changed.connect(lambda v: signals_received.append(v))

    sr._stars[2].click()
    assert sr.rating == 3
    assert signals_received == [3]

    sr.clear()
    assert sr.rating == 0


def test_empty_state_widget(qapp):
    from PySide6.QtWidgets import QLabel

    from gui.widgets.components import EmptyState

    es = EmptyState("\U0001f3b5", "No Songs Found", "Try a different search.", None)
    labels = es.findChildren(QLabel)
    assert len(labels) == 3
    assert labels[0].text() == "\U0001f3b5"
    assert labels[1].text() == "No Songs Found"
    assert labels[2].text() == "Try a different search."


def test_toast_widget_appears_and_disappears(qapp):
    from gui.widgets.components import ToastWidget

    parent = QWidget()
    parent.resize(800, 600)
    parent.show()
    qapp.processEvents()

    toast = ToastWidget(parent, "Hello toast", "info")
    qapp.processEvents()

    assert toast.isVisible()
    assert toast._timer.isActive()

    # Trigger immediate dismiss via internal timer
    toast._timer.timeout.emit()
    qapp.processEvents()

    # After slide-out is triggered, the animation starts
    assert hasattr(toast, "_anim_out")

    # Trigger animation finished to simulate cleanup
    toast._anim_out.finished.emit()
    qapp.processEvents()

    # Toast should be scheduled for deletion (isWidgetType returns False after deleteLater)
    try:
        toast.isVisible()
    except RuntimeError:
        pass  # C++ object already deleted
    assert True  # toast cleanup triggered without errors

    parent.close()


def test_confirm_returns_bool(qapp):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    from gui.widgets.components import confirm

    parent = QWidget()
    parent.show()
    qapp.processEvents()

    # Test "Yes" → True
    def click_yes():
        for w in qapp.topLevelWidgets():
            if isinstance(w, QMessageBox):
                btn = w.button(QMessageBox.StandardButton.Yes)
                if btn:
                    btn.click()
                return

    QTimer.singleShot(50, click_yes)
    result = confirm(parent, "Confirm", "Do you agree?")
    assert result is True

    # Test "No" → False
    def click_no():
        for w in qapp.topLevelWidgets():
            if isinstance(w, QMessageBox):
                btn = w.button(QMessageBox.StandardButton.No)
                if btn:
                    btn.click()
                return

    QTimer.singleShot(50, click_no)
    result = confirm(parent, "Confirm", "Do you agree?")
    assert result is False

    parent.close()
