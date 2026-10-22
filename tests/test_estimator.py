import copy
import unittest
from datetime import datetime, timedelta, timezone
from campura_vision.estimator import InputError, estimate, stamp
from campura_vision.samples import example, NAMES

NOW = datetime(2026, 10, 20, 4, 0, tzinfo=timezone.utc)


class EstimatorTests(unittest.TestCase):
    def data(self, name='dining'):
        data = example(name, NOW)
        data['capacity']['variation'] = 0
        return data

    def calc(self, data):
        return estimate(data, NOW)

    def test_original_16_orders_two_slots(self):
        result = self.calc(self.data())
        self.assertEqual(result['backlog'], 16)
        self.assertEqual(result['preorder']['minutes'], [13.5, 13.5])

    def test_single_slot_and_three_slots(self):
        data = self.data()
        data['capacity']['prep_slots'] = 1
        self.assertEqual(self.calc(data)['preorder']['minutes'], [25.5, 25.5])
        data['capacity']['prep_slots'] = 3
        self.assertEqual(self.calc(data)['preorder']['minutes'], [9, 9])

    def test_dedup_latest_ready_removes_backlog(self):
        data = self.data()
        event = copy.deepcopy(data['orders']['events'][0])
        data['orders']['events'].append(copy.deepcopy(event))
        self.assertEqual(self.calc(data)['backlog'], 16)
        event.update(status='ready', updated_at=stamp(NOW), ready_at=stamp(NOW))
        data['orders']['events'].append(event)
        self.assertEqual(self.calc(data)['backlog'], 15)
        self.assertEqual(self.calc(data)['preorder']['minutes'], [12, 12])

    def test_in_progress_uses_remaining_and_original_placed_time(self):
        data = self.data('preparing')
        result = self.calc(data)
        self.assertEqual(result['backlog'], 16)
        self.assertEqual(result['preorder']['parts']['从现在还需等待'], [0.3, 0.3])
        self.assertEqual(result['preorder']['minutes'], [20.3, 20.3])
        self.assertEqual(result['preorder']['new_order_minutes'], [12.3, 12.3])

    def test_pending_does_not_get_eta(self):
        result = self.calc(self.data('pending'))
        self.assertEqual(result['preorder']['status'], 'pending')
        self.assertIsNone(result['preorder']['minutes'])
        self.assertEqual(result['backlog'], 16)

    def test_accepted_existing_target_is_not_new_order(self):
        data = self.data()
        data['preorder_order_id'] = 'demo-order-00'
        result = self.calc(data)['preorder']
        self.assertEqual(result['parts']['从现在还需等待'], [1.5, 1.5])
        self.assertEqual(result['minutes'], [21.5, 21.5])

    def test_future_orders_do_not_delay_preorder(self):
        data = self.data()
        original = self.calc(data)
        data['forecast']['online_orders_per_minute'] = [4, 4]
        changed = self.calc(data)
        self.assertEqual(original['preorder']['minutes'], changed['preorder']['minutes'])
        self.assertGreater(changed['arrival_route']['minutes'][0], original['arrival_route']['minutes'][0])

    def test_travel_allows_backlog_to_clear_and_excludes_travel(self):
        data = self.data()
        data['service_queue']['waiting'] = 0
        data['forecast']['online_orders_per_minute'] = [0, 0]
        data['forecast']['walk_in_orders_per_minute'] = [0, 0]
        data['arrival_minutes'] = 30
        result = self.calc(data)
        self.assertEqual(result['arrival_route']['minutes'], [2, 2])
        self.assertEqual(result['travel_minutes'], 30)
        self.assertGreater(result['arrival_now']['minutes'][0], 2)

    def test_occupancy_and_page_views_not_counted_as_orders(self):
        data = self.data()
        original = self.calc(data)
        data['vision']['occupancy'] = 900
        data['vision']['queue_people'] = 800
        data['page_views']['active_people'] = 90000
        changed = self.calc(data)
        for key in ('preorder', 'arrival_now', 'arrival_route'):
            self.assertEqual(original[key]['minutes'], changed[key]['minutes'])

    def test_missing_conversion_or_queue_progress_no_total(self):
        for change in ('unit', 'busy_remaining_minutes'):
            data = self.data()
            data['service_queue'].pop(change)
            result = self.calc(data)
            self.assertIsNone(result['arrival_now']['minutes'])
            self.assertIsNotNone(result['preorder']['minutes'])

    def test_queue_transactions_only_join_kitchen_once(self):
        data = self.data()
        data['orders']['events'] = []
        data['capacity'].update(prep_slots=1, prep_minutes=1, order_minutes=1)
        data['service_queue']['waiting'] = 2
        data['forecast']['online_orders_per_minute'] = [0, 0]
        data['forecast']['walk_in_orders_per_minute'] = [0, 0]
        # Two ahead accept at t=1,2 and finish at t=2,3; own accepts at 3, finishes at 4.
        self.assertEqual(self.calc(data)['arrival_now']['minutes'], [4, 4])

    def test_current_cashier_work_and_queue_clear_during_selection(self):
        data = self.data('retail')
        result = self.calc(data)
        self.assertEqual(result['arrival_now']['minutes'], [3.2, 6.6])
        self.assertEqual(result['arrival_route']['minutes'], [1.6, 6.6])
        self.assertIsNone(result['preorder']['minutes'])

    def test_retail_future_joiners_change_future_checkout(self):
        quiet = self.calc(self.data('retail'))
        busy = self.calc(self.data('retail_growth'))
        self.assertGreater(busy['arrival_route']['minutes'][1], quiet['arrival_route']['minutes'][1])

    def test_calibration_same_crowding_bin_minimum_samples(self):
        data = self.data('calibrated')
        result = self.calc(data)
        self.assertEqual(result['selection']['matching_samples'], 40)
        self.assertEqual(result['selection']['minutes'], [2.1, 3.7])
        data['calibration']['samples'] = data['calibration']['samples'][:29]
        self.assertEqual(self.calc(data)['selection']['minutes'], [1, 6])
        data = self.data('calibrated')
        data['vision']['space_occupancy_ratio'] = 0.8
        self.assertEqual(self.calc(data)['selection']['minutes'], [1, 6])

    def test_partial_coverage_keeps_checkout_segment(self):
        result = self.calc(self.data('partial'))
        self.assertIsNone(result['arrival_now']['minutes'])
        self.assertIn('挑选后排队及结账', result['arrival_now']['parts'])
        self.assertEqual(result['arrival_now']['status'], 'partial')

    def test_disconnect_then_fresh_snapshot_recovers(self):
        stale = self.calc(self.data('stale'))
        self.assertIsNone(stale['preorder']['minutes'])
        self.assertIsNone(stale['arrival_now']['minutes'])
        fresh = self.calc(self.data())
        self.assertIsNotNone(fresh['preorder']['minutes'])
        self.assertIsNotNone(fresh['arrival_now']['minutes'])

    def test_independent_freshness(self):
        data = self.data()
        data['vision']['observed_at'] = stamp(NOW - timedelta(seconds=31))
        self.assertIsNone(self.calc(data)['arrival_now']['minutes'])
        self.assertIsNotNone(self.calc(data)['preorder']['minutes'])
        data = self.data()
        data.pop('forecast')
        self.assertIsNone(self.calc(data)['arrival_now']['minutes'])
        self.assertIsNotNone(self.calc(data)['preorder']['minutes'])

    def test_bad_order_state_no_total(self):
        data = self.data('preparing')
        data['orders']['events'][-2].pop('remaining_minutes')
        self.assertIsNone(self.calc(data)['preorder']['minutes'])
        data = self.data()
        data['orders']['complete'] = False
        self.assertIsNone(self.calc(data)['preorder']['minutes'])

    def test_same_time_conflicting_events_rejected(self):
        data = self.data()
        event = copy.deepcopy(data['orders']['events'][0])
        event['status'] = 'cancelled'
        data['orders']['events'].append(event)
        self.assertIsNone(self.calc(data)['preorder']['minutes'])

    def test_missing_order_status_preserves_counts_and_ordering_segment(self):
        data = self.data()
        data['orders']['events'][0].pop('status')
        result = self.calc(data)
        self.assertIsNone(result['preorder']['minutes'])
        self.assertEqual(result['counts']['queue_people'], 3)
        self.assertIn('排队及点单', result['arrival_now']['parts'])

    def test_invalid_numeric_and_timestamps(self):
        for bad in (True, float('nan'), float('inf'), -1, 0, 51, '2', 1.5):
            data = self.data()
            data['capacity']['prep_slots'] = bad
            with self.subTest(bad=bad), self.assertRaises(InputError):
                self.calc(data)
        data = self.data()
        data['orders']['observed_at'] = '2026-10-20T04:00:00'
        with self.assertRaises(InputError):
            self.calc(data)

    def test_unknown_route_not_zero(self):
        data = self.data()
        data.pop('arrival_minutes')
        self.assertIsNone(self.calc(data)['arrival_route']['minutes'])

    def test_all_examples_and_bounds(self):
        for name in NAMES:
            with self.subTest(name=name):
                result = self.calc(example(name, NOW))
                for key in ('preorder', 'arrival_now', 'arrival_route'):
                    value = result[key]['minutes']
                    if value:
                        self.assertGreaterEqual(value[0], 0)
                        self.assertLessEqual(value[0], value[1])


if __name__ == '__main__':
    unittest.main()
