import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('simulator', Path(__file__).with_name('offline_jeju_simulator.py'))
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


class SimTests(unittest.TestCase):
    def test_first_positive(self):
        self.assertEqual(sim.transition(None, 4), (4, 'FIRST_POSITIVE'))

    def test_first_zero(self):
        self.assertEqual(sim.transition(None, 0), (0, None))

    def test_increase(self):
        self.assertEqual(sim.transition(2, 5), (5, 'INCREASE'))

    def test_decrease(self):
        self.assertEqual(sim.transition(5, 2), (2, 'DECREASE'))

    def test_sold_out(self):
        self.assertEqual(sim.transition(2, 0), (0, 'SOLD_OUT'))

    def test_no_change(self):
        self.assertEqual(sim.transition(2, 2), (2, None))

    def test_unknown_preserves_state(self):
        self.assertEqual(sim.apply({'12345': 4}, '12345', None), ({'12345': 4}, None))

    def test_failed_delivery_preserves_state(self):
        self.assertEqual(sim.apply({'12345': 4}, '12345', 0, delivered=False), ({'12345': 4}, 'ALERT_PENDING'))

    def test_retry_after_failed_delivery(self):
        state, _ = sim.apply({'12345': 4}, '12345', 0, delivered=False)
        self.assertEqual(sim.apply(state, '12345', 0), ({'12345': 0}, 'SOLD_OUT'))

    def test_other_product_rejected(self):
        with self.assertRaises(ValueError):
            sim.transition(1, 2, '0000000000000')

    def test_invalid_negative_rejected(self):
        with self.assertRaises(ValueError):
            sim.transition(1, -1)

    def test_invalid_boolean_rejected(self):
        with self.assertRaises(ValueError):
            sim.transition(1, False)

    def test_isolated_store(self):
        self.assertEqual(sim.apply({'11111': 2, '22222': 9}, '11111', 0)[0], {'11111': 0, '22222': 9})


if __name__ == '__main__':
    unittest.main()
