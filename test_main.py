import unittest

import cv2

import main


class TargetSelectionBehaviorTests(unittest.TestCase):
    def test_should_not_auto_detect_before_initial_selection(self):
        self.assertFalse(main.should_auto_detect_target(waiting_for_selection=True, target_locked=False))

    def test_should_auto_detect_after_initial_selection_is_done(self):
        self.assertTrue(main.should_auto_detect_target(waiting_for_selection=False, target_locked=False))

    def test_should_stop_auto_detection_after_target_is_locked(self):
        self.assertFalse(main.should_auto_detect_target(waiting_for_selection=False, target_locked=True))

    def test_new_selection_overrides_previous_locked_target(self):
        main.CURRENT_TARGET = (10, 10, 50, 50, (35, 35))
        main.TARGET_LOCKED = True
        main.TARGET_TEMPLATE = object()

        main.select_target_from_click(cv2.EVENT_LBUTTONDOWN, 10, 10, None, None)
        main.select_target_from_click(cv2.EVENT_MOUSEMOVE, 120, 80, None, None)
        main.select_target_from_click(cv2.EVENT_LBUTTONUP, 120, 80, None, None)

        self.assertIsNotNone(main.SELECTED_TARGET)
        self.assertIsNone(main.CURRENT_TARGET)
        self.assertFalse(main.TARGET_LOCKED)
        self.assertIsNone(main.TARGET_TEMPLATE)


if __name__ == "__main__":
    unittest.main()
