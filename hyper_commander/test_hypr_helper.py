import unittest
from hypr_helper import check_position, matches_position

class TestHyprHelper(unittest.TestCase):
    def test_check_position_top_left(self):
        # Top-left is rx < 0.5, ry < 0.5
        self.assertTrue(check_position(0.25, 0.25, "topleft"))
        self.assertTrue(check_position(0.1, 0.49, "top-left"))
        self.assertFalse(check_position(0.6, 0.25, "top-left"))
        self.assertFalse(check_position(0.25, 0.6, "top-left"))

    def test_check_position_bottom_left(self):
        # Bottom-left is rx < 0.5, ry >= 0.5
        self.assertTrue(check_position(0.25, 0.75, "bottomleft"))
        self.assertTrue(check_position(0.1, 0.5, "bottom-left"))
        self.assertFalse(check_position(0.6, 0.75, "bottom-left"))
        self.assertFalse(check_position(0.25, 0.4, "bottom-left"))

    def test_check_position_top_right(self):
        # Top-right is rx >= 0.5, ry < 0.5
        self.assertTrue(check_position(0.75, 0.25, "topright"))
        self.assertTrue(check_position(0.5, 0.49, "top-right"))
        self.assertFalse(check_position(0.4, 0.25, "top-right"))
        self.assertFalse(check_position(0.75, 0.6, "top-right"))

    def test_check_position_bottom_right(self):
        # Bottom-right is rx >= 0.5, ry >= 0.5
        self.assertTrue(check_position(0.75, 0.75, "bottomright"))
        self.assertTrue(check_position(0.5, 0.5, "bottom-right"))
        self.assertFalse(check_position(0.4, 0.75, "bottom-right"))
        self.assertFalse(check_position(0.75, 0.4, "bottom-right"))

    def test_check_position_left_right_top_bottom(self):
        # Left
        self.assertTrue(check_position(0.4, 0.5, "left"))
        self.assertFalse(check_position(0.6, 0.5, "left"))
        # Right
        self.assertTrue(check_position(0.6, 0.5, "right"))
        self.assertFalse(check_position(0.4, 0.5, "right"))
        # Top
        self.assertTrue(check_position(0.5, 0.4, "top"))
        self.assertFalse(check_position(0.5, 0.6, "top"))
        # Bottom
        self.assertTrue(check_position(0.5, 0.6, "bottom"))
        self.assertFalse(check_position(0.5, 0.4, "bottom"))

    def test_check_position_center(self):
        # Center: 0.25 <= rx <= 0.75 and 0.25 <= ry <= 0.75
        self.assertTrue(check_position(0.5, 0.5, "center"))
        self.assertTrue(check_position(0.3, 0.7, "middle"))
        self.assertFalse(check_position(0.1, 0.5, "center"))
        self.assertFalse(check_position(0.5, 0.9, "center"))

    def test_matches_position_multiple(self):
        # Matches if at least one pos matches
        self.assertTrue(matches_position(0.2, 0.2, ["top-left", "bottom-right"]))
        self.assertTrue(matches_position(0.8, 0.8, ["top-left", "bottom-right"]))
        self.assertFalse(matches_position(0.2, 0.8, ["top-left", "bottom-right"]))
        
        # Empty matches everything
        self.assertTrue(matches_position(0.2, 0.8, []))

if __name__ == "__main__":
    unittest.main()
