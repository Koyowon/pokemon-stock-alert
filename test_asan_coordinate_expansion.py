import unittest
from asan_coordinate_expansion import build_points, expansion_audit
from cu_stock_monitor import POINTS

class CoordinateExpansionTests(unittest.TestCase):
    def test_default_preserves_only_original_points(self):
        self.assertEqual(build_points(), POINTS["아산"])
    def test_provisional_adds_only_three_registry_coordinates(self):
        points=build_points(include_provisional=True)
        self.assertEqual(len(points),10)
        self.assertEqual(points[:7],POINTS["아산"])
    def test_duplicate_coordinate_not_added(self):
        s=[{"monitor_candidate":True,"latitude":36.790,"longitude":127.000}]
        self.assertEqual(build_points(include_provisional=True,stores=s),POINTS["아산"])
    def test_invalid_coordinate_ignored(self):
        s=[{"monitor_candidate":True,"latitude":"garbage","longitude":"127"},
           {"monitor_candidate":True,"latitude":"99","longitude":"127"}]
        self.assertEqual(build_points(include_provisional=True,stores=s),POINTS["아산"])
    def test_audit_marks_unverified(self):
        result=expansion_audit()
        self.assertEqual(result["candidates"],119)
        self.assertEqual(len(result["provisional_coordinate_candidates"]),3)
        self.assertTrue(all(not p["verified"] for p in result["provisional_coordinate_candidates"]))
if __name__=="__main__":
    unittest.main()
