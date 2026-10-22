"""Fresh, entirely fabricated examples. No production identifiers or footage."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from .estimator import stamp

NAMES = {
    'dining': '餐饮 · 7 单线上 + 9 单线下',
    'preparing': '餐饮 · 正在制作与重复订单事件',
    'pending': '餐饮 · 预订单待确认',
    'retail': '零售 · 挑选期间队伍消退',
    'retail_growth': '零售 · 新顾客陆续结账',
    'calibrated': '零售 · 匿名模拟样本校准',
    'partial': '零售 · 机位覆盖不足',
    'stale': '餐饮 · 断流与数据过期',
}


def example(name='dining', now=None):
    if name not in NAMES:
        raise ValueError('未知示例')
    now = now or datetime.now(timezone.utc)
    current = stamp(now)
    data = {
        'schema_version': 1, 'mode': 'simulation', 'kind': 'dining', 'arrival_minutes': 8,
        'capacity': {'prep_minutes': 1.5, 'prep_slots': 2, 'order_minutes': 0.5,
                     'order_slots': 1, 'checkout_minutes': 0.6, 'checkout_slots': 1, 'variation': 0.2},
        'orders': {'observed_at': current, 'complete': True, 'events': []},
        'vision': {'observed_at': current, 'scene': 'whole_store',
                   'coverage': ['entrance', 'shopping', 'checkout', 'ordering'],
                   'occupancy': 12, 'queue_people': 3, 'space_occupancy_ratio': 0.42},
        'service_queue': {'observed_at': current, 'scope': 'ordering', 'unit': 'transactions',
                          'waiting': 2, 'busy_remaining_minutes': []},
        'forecast': {'observed_at': current, 'basis': 'simulation',
                     'online_orders_per_minute': [0.1, 0.4], 'walk_in_orders_per_minute': [0.1, 0.3],
                     'checkout_arrivals_per_minute': [0, 0]},
        'page_views': {'observed_at': current, 'active_people': 18},
        'calibration': {'observed_at': current, 'samples': []},
        'preorder_order_id': None,
    }
    for i in range(16):
        at = stamp(now - timedelta(minutes=20 - i))
        data['orders']['events'].append({'id': 'demo-order-%02d' % i,
            'channel': 'online' if i < 7 else 'offline', 'status': 'accepted',
            'placed_at': at, 'accepted_at': at, 'updated_at': at})
    if name == 'preparing':
        for i, remaining in enumerate([0.3, 0.8]):
            event = deepcopy(data['orders']['events'][i])
            event.update(status='preparing', updated_at=current, remaining_minutes=remaining)
            data['orders']['events'].append(event)
        data['orders']['events'].append(deepcopy(data['orders']['events'][0]))
        data['preorder_order_id'] = 'demo-order-00'
    elif name == 'pending':
        data['orders']['events'].append({'id': 'demo-pending', 'status': 'pending',
                                        'placed_at': current, 'updated_at': current})
        data['preorder_order_id'] = 'demo-pending'
    if name in ('retail', 'retail_growth', 'calibrated', 'partial'):
        data['kind'] = 'retail'
        data['service_queue'].update(scope='checkout', waiting=4, busy_remaining_minutes=[0.2])
        data['vision']['queue_people'] = 6
        data.pop('orders')
        if name in ('retail_growth', 'calibrated'):
            data['forecast']['checkout_arrivals_per_minute'] = [0.7, 1.8]
        if name == 'calibrated':
            data['calibration']['samples'] = [
                {'minutes': 2 + (i % 10) * 0.2, 'space_occupancy_ratio': 0.42} for i in range(40)]
        if name == 'partial':
            data['vision']['coverage'] = ['checkout']
    if name == 'stale':
        data['vision']['observed_at'] = stamp(now - timedelta(minutes=3))
        data['orders']['observed_at'] = stamp(now - timedelta(minutes=3))
        data['service_queue']['observed_at'] = stamp(now - timedelta(minutes=3))
    return data
