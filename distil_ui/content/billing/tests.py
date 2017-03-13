# Copyright (c) 2014 Catalyst IT Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import math
import time

from mox3 import mox

from distil_ui.api import distil
from openstack_dashboard.test import helpers as test


class FakeUser(object):
    roles = [{'name': 'admin'}]


class FakeRequest(object):
    user = FakeUser()


class FakeDistilClient(object):
    """A fake distil client for unit test."""
    endpoint = 'http://localhost:8788'
    request = FakeRequest()

    def get_rated(self, tenant, start, end):
        raise NotImplemented()


class BillingTests(test.TestCase):
    """FIXME(flwang): Move this test to rest_api_tests.py

    Now we're putting the api test at here, since we don't want to hack
    horizon too much. That means we don't want to put the api.py under /api
    folder, at least for now.
    """

    def setUp(self):
        super(BillingTests, self).setUp()
        self.mocker = mox.Mox()

    def test_calculate_end_date(self):
        start = datetime.date(2015, 1, 1)
        end = distil._calculate_end_date(start)
        self.assertEqual((end.year, end.month, end.day), (2015, 2, 1))

        start = datetime.date(2015, 6, 1)
        end = distil._calculate_end_date(start)
        self.assertEqual((end.year, end.month, end.day), (2015, 7, 1))

        start = datetime.date(2015, 12, 1)
        end = distil._calculate_end_date(start)
        self.assertEqual((end.year, end.month, end.day), (2016, 1, 1))

    def test_get_month_cost(self):
        distilclient = self.mocker.CreateMock(FakeDistilClient)

        resources = {"fake_uuid_1": {"services": [{
                                     "volume": 2100,
                                     "rate": 0.0005,
                                     "cost": 1.05,
                                     "name": "b1.standard",
                                     "unit": "gigabyte"}],
                                     "total_cost": 1.05,
                                     "type": "Image",
                                     "name": "cirros"},
                     "fake_uuid_2": {"services": [{
                                     "volume": 122,
                                     "rate": 0.048,
                                     "cost": 5.86,
                                     "name": "m1.tiny",
                                     "unit": "hour"}],
                                     "total_cost": 5.86,
                                     "type": "Virtual Machine",
                                     "name": "dfgh"},
                     "fake_uuid_3": {"services": [{
                                     "volume": 200,
                                     "rate": 0.048,
                                     "cost": 9.60,
                                     "name": "m1.tiny",
                                     "unit": "hour"}],
                                     "total_cost": 9.60,
                                     "type": "Virtual Machine",
                                     "name": "abcd"},
                     "fake_uuid_4": {"services": [{"volume": 20.00,
                                                   "rate": 0.016,
                                                   "cost": 0.32,
                                                   "name": "n1.network",
                                                   "unit": "hour"},
                                                  {"volume": 10.00,
                                                   "rate": 0.016,
                                                   "cost": 0.16,
                                                   "name": "n1.network",
                                                   "unit": "hour"}],
                                     "total_cost": 0.48,
                                     "type": "Network",
                                     "name": "public"}
                     }

        result = {'usage': {"end": "2011-03-01 00:00:00", "name": "openstack",
                            "total_cost": 7.23,
                            "tenant_id": "7c3c506ad4b943f5bb12b9fb69478084",
                            "start": "2011-02-01 00:00:00",
                            "resources": resources
                            }
                  }

        distilclient.get_rated([self.tenant.id],
                               '2011-02-01T00:00:00',
                               '2011-03-01T00:00:00').AndReturn(result)
        self.mocker.ReplayAll()

        cost = [()]
        distil._get_month_cost(distilclient,
                               self.tenant.id,
                               '2011-02-01T00:00:00',
                               '2011-03-01T00:00:00',
                               cost, 0)
        self.assertEqual(16.99, cost[0][0])
        self.assertEqual(3, len(cost[0][1]))
        bill_items = {}
        for b in cost[0][1]:
            # Convert cost to string make sure the floating number is right
            bill_items[b.resource] = (b.count, str(b.cost))

        self.assertEqual((2, '0.48'), bill_items['Network'])
        self.assertEqual((2, '15.46'), bill_items['Compute'])
        self.assertEqual((1, '1.05'), bill_items['Image'])

    def test_calculate_history_date(self):
        """Using the same algorithm to calculate the history date."""
        today = datetime.date(2015, 2, 17)
        start = distil._calculate_start_date(datetime.date(2015, 2, 17))
        end = distil._calculate_end_date(start)
        final_end = datetime.datetime(today.year, today.month + 1, 1)

        history_date = [None for i in range(12)]
        for i in range(12):
            start_str = start.strftime("%Y-%m-%dT00:00:00")
            end_str = end.strftime("%Y-%m-%dT00:00:00")
            history_date[i] = (start_str, end_str)
            start = end
            end = distil._calculate_end_date(start)
            if end > final_end:
                break

        self.assertEqual(('2014-03-01T00:00:00', '2014-04-01T00:00:00'),
                         history_date[0])
        self.assertEqual(('2014-04-01T00:00:00', '2014-05-01T00:00:00'),
                         history_date[1])
        self.assertEqual(('2014-05-01T00:00:00', '2014-06-01T00:00:00'),
                         history_date[2])
        self.assertEqual(('2014-06-01T00:00:00', '2014-07-01T00:00:00'),
                         history_date[3])
        self.assertEqual(('2014-07-01T00:00:00', '2014-08-01T00:00:00'),
                         history_date[4])
        self.assertEqual(('2014-08-01T00:00:00', '2014-09-01T00:00:00'),
                         history_date[5])
        self.assertEqual(('2014-09-01T00:00:00', '2014-10-01T00:00:00'),
                         history_date[6])
        self.assertEqual(('2014-10-01T00:00:00', '2014-11-01T00:00:00'),
                         history_date[7])
        self.assertEqual(('2014-11-01T00:00:00', '2014-12-01T00:00:00'),
                         history_date[8])
        self.assertEqual(('2014-12-01T00:00:00', '2015-01-01T00:00:00'),
                         history_date[9])
        self.assertEqual(('2015-01-01T00:00:00', '2015-02-01T00:00:00'),
                         history_date[10])
        self.assertEqual(('2015-02-01T00:00:00', '2015-03-01T00:00:00'),
                         history_date[11])

    def test_get_cost(self):
        distilclient = self.mocker.CreateMock(FakeDistilClient)

        today = datetime.date.today()
        start = distil._calculate_start_date(datetime.date.today())
        end = distil._calculate_end_date(start)
        final_end = datetime.datetime(today.year, today.month + 1, 1)

        for i in range(12):
            result = {'usage': {'total_cost': (i + 1) * 100,
                                'resources': {'uuid': {"services": [{
                                                       "volume": 2100,
                                                       "rate": 0.0005,
                                                       "cost": 1.05,
                                                       "name": "b1.standard",
                                                       "unit": "gigabyte"}],
                                                       "total_cost": 1.05,
                                                       "type": "Image",
                                                       "name": "cirros"}}}}
            start_str = start.strftime("%Y-%m-%dT00:00:00")
            end_str = end.strftime("%Y-%m-%dT00:00:00")
            distilclient.get_rated([self.tenant.id],
                                   start_str,
                                   end_str).AndReturn(result)

            start = end
            end = distil._calculate_end_date(start)
            if end > final_end:
                break

        self.mocker.ReplayAll()
        setattr(self.request.user, 'tenant_id', self.tenant.id)
        history_cost = distil.get_cost(self.request,
                                       distil_client=distilclient,
                                       enable_eventlet=False)
        # 2 = math.ceil(1.05)
        self.assertEqual([1.05 for i in range(12)],
                         [c[0] for c in history_cost])

    def test_apply_discount(self):
        # There are 3 scenarios for current month.
        cost = (47.54,
                [distil.BILLITEM(id=1, resource='Compute', count=9,
                                 cost=31.76),
                 distil.BILLITEM(id=2, resource=u'Network', count=3, cost=1.5),
                 distil.BILLITEM(id=3, resource=u'Image', count=35, cost=3.82),
                 distil.BILLITEM(id=4, resource=u'Router', count=2, cost=0.96),
                 distil.BILLITEM(id=5, resource=u'Floating IP', count=21,
                                 cost=3.57),
                 distil.BILLITEM(id=6, resource='Block Storage', count=22,
                                 cost=6.08)
                 ], [])
        prices = {u'Virtual Machine': 0.044, u'Network': 0.016,
                  u'Image': 0.0005, u'Volume': 0.0005,
                  u'Router': 0.017, u'Floating IP': 0.006}
        start_str = '2015-07-01T00:00:00'
        end_str = '2015-07-02T04:00:00'

        cost_after_discount = distil._apply_discount(cost, start_str, end_str,
                                                     prices)
        start = time.mktime(time.strptime(start_str, '%Y-%m-%dT%H:%M:%S'))
        end = time.mktime(time.strptime(end_str, '%Y-%m-%dT%H:%M:%S'))
        free_hours = math.floor((end - start) / 3600)

        free_network_cost = round(0.016 * free_hours, 2)
        free_router_cost = round(0.017 * free_hours, 2)

        self.assertEqual(cost[0] - free_network_cost - free_router_cost,
                         cost_after_discount[0])

        self.assertIn(distil.BILLITEM(id=2, resource=u'Network', count=3,
                                      cost=1.05),
                      cost_after_discount[1])
        self.assertIn(distil.BILLITEM(id=4, resource=u'Router', count=2,
                                      cost=0.48),
                      cost_after_discount[1])

    def test_get_month_cost_with_cache(self):
        distil.CACHE.clear()
        distilclient = self.mocker.CreateMock(FakeDistilClient)
        result = {'usage': {'total_cost': 5.05,
                            'resources': {'uuid':
                                          {"services": [{"volume": 2100,
                                                         "rate": 0.0005,
                                                         "cost": 5.05,
                                                         "name": "b1.standard",
                                                         "unit": "gigabyte"}],
                                           "total_cost": 5.05,
                                           "type": "Image",
                                           "name": "cirros"}}}}
        distilclient.get_rated([self.tenant.id],
                               '2011-02-01T00:00:00',
                               '2011-03-01T00:00:00').AndReturn(result)
        self.mocker.ReplayAll()

        cost = [()]
        distil._get_month_cost(distilclient,
                               self.tenant.id,
                               '2011-02-01T00:00:00',
                               '2011-03-01T00:00:00',
                               cost, 0)
        key = 'http://localhost:8788_1_2011-02-01T00:00:00_2011-03-01T00:00:00'
        self.assertIn(key, distil.CACHE)
        self.assertEqual(distil.CACHE[key][0], 5.05)
