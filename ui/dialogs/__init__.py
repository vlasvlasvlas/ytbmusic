"""
Dialogs Package

UI dialog components for YTBMusic.
"""

# Existing dialogs
from ui.dialogs.input_dialog import InputDialog
from ui.dialogs.confirm_dialog import ConfirmDialog

# New dialogs extracted from main.py
from ui.dialogs.list_dialog import ListDialog
from ui.dialogs.modal_overlay import ModalOverlay
from ui.dialogs.track_picker import TrackPickerDialog

__all__ = [
    "InputDialog",
    "ConfirmDialog",
    "ListDialog",
    "ModalOverlay",
    "TrackPickerDialog",
]
