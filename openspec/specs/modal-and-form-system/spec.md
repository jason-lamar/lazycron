# Modal and Form System Specification

## Status

Current state: `implemented` for edit modal, new job wizard, visual cron builder, search overlay, help dialog, quit confirmation, and Run Now output modal. All key logic is tested in `test_modals.py` (4 tests for form state navigation).

## Requirements

### Requirement: Edit modal with integrated 5-field schedule form

The edit modal SHALL display a 5-field cron schedule form with individual input boxes, preset picklist per field, live validation preview, raw expression display, and name/command text fields.

Evidence:
- `lazycron/ui/modals.py:744-770` — `show_edit_modal()` parses existing schedule into 5 fields, creates `_FormState`, runs form loop.
- `lazycron/ui/modals.py:360-491` — `_FormState` manages field values, preset indices, cursor positions, validation, and navigation between 7 form elements (5 cron + name + command).
- `lazycron/ui/modals.py:107-212` — `_draw_field_box()` renders a 3-row field box with label, border, and centered value. `_draw_text_field()` renders label + bordered text input with wrapping and scroll.
- `lazycron/ui/modals.py:217-355` — `_show_picklist()` renders a scrollable dropdown with presets and labels, arrow-key navigation, and Tab/Escape/Enter handling.
- `lazycron/ui/modals.py:494-739` — `_run_form()` main form loop: renders all fields, preview, hints, handles Tab/Shift+Tab navigation, vertical movement between field rows, character typing, paste detection (`_drain_paste`), clipboard paste (`Ctrl+V`), preset cycling (Up/Down on cron fields), and Ctrl+S/Enter submission.

### Requirement: Visual cron builder with odometer-style field selector

The cron builder SHALL display 5 columns, each cycling through preset values, with live human-readable preview and custom value entry.

Evidence:
- `lazycron/ui/cronbuilder.py:33-185` — `show_cron_builder()` renders columns with field labels, up/down arrows, centered values, and live description preview.
- `lazycron/ui/cronbuilder.py:188-197` — `_cycle_field()` cycles through preset list for a field.
- `lazycron/ui/cronbuilder.py:200-254` — `_custom_value_input()` allows typing a custom value with backspace, cursor movement, and Enter confirmation.

### Requirement: Search/filter overlay with text input

The search modal SHALL provide a single-line text input for filtering jobs, with Escape to cancel and Enter to apply.

Evidence:
- `lazycron/ui/modals.py:797-813` — `show_search_modal()` creates a centered overlay with filter input.
- `lazycron/ui/modals.py:1002-1072` — `_text_input()` handles single-line text input with cursor movement, backspace, delete, home/end, clipboard paste, paste burst detection.

### Requirement: Delete confirmation requires two presses

The system SHALL require two presses of `d` within 3 seconds to confirm deletion, preventing accidental removals.

Evidence:
- `lazycron/state.py:78,157-178` — `delete_pending` timestamp with 3-second TTL. First press sets pending and shows message; second press within window confirms.
- `lazycron/ui/statusbar.py:34` — Shows "Press d again to confirm delete" when pending.

### Requirement: Dirty-quit confirmation

When quitting with unsaved changes, the system SHALL show a confirmation modal with options to quit (q), save and quit (s), or cancel (Esc).

Evidence:
- `lazycron/app.py:157-162` — Main loop checks `store.dirty` before quitting.
- `lazycron/ui/modals.py:860-887` — `show_quit_confirm()` renders modal with q/s/Esc options.

### Requirement: Help modal shows all keybindings

The help modal SHALL display a comprehensive list of keybindings organized by action.

Evidence:
- `lazycron/ui/modals.py:816-857` — `show_help_modal()` renders 15 keybinding entries with key and description columns.

### Requirement: Run Now output modal shows command results

After executing a job via Shift+R, the system SHALL display a modal with the command that was run, exit code, stdout/stderr output, and macOS provenance hints when applicable.

Evidence:
- `lazycron/ui/modals.py:890-927` — `show_run_output_modal()` renders command, exit code (green/red), output lines, and macOS 126 hint.

### Requirement: Paste detection handles terminal paste bursts

When text is pasted into the terminal, the system SHALL detect the burst and combine all characters into a single paste operation rather than treating each character as a separate input.

Evidence:
- `lazycron/ui/modals.py:29-48` — `_drain_paste()` enables nodelay mode and reads all immediately-available characters.
- `lazycron/ui/modals.py:729-739` — `_run_form()` detects bursts (>1 char) and redirects to command field.
- `lazycron/ui/modals.py:1067-1072` — `_text_input()` also drains paste bursts.

## Non-Requirements

- The form system does not support multi-tab edit modes for different job types.
- The picklist does not support custom user-defined presets beyond the hardcoded lists.
- The Run Now modal is read-only — output cannot be copied to clipboard from within curses.
