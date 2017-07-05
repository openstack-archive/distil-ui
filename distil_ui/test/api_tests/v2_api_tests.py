# Copyright (c) 2017 Catalyst IT Ltd.
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

from distil_ui.api import distil_v2
from freezegun import freeze_time
from openstack_dashboard.test import helpers as test

import mock

regionOne = mock.Mock(id='RegionOne')
regionTwo = mock.Mock(id='RegionTwo')
region_list = [regionOne, regionTwo]
fake_keystoneclient = mock.MagicMock()
fake_keystoneclient.regions.list = mock.Mock(return_value=region_list)
get_fake_keystoneclient = mock.Mock(return_value=fake_keystoneclient)


class FakeDistilClient(mock.MagicMock):
    def __init__(self, *args, **kwargs):
        super(FakeDistilClient, self).__init__(*args, **kwargs)
        self.region_id = kwargs.get('region_id')
        self.quotations = mock.MagicMock()
        if self.region_id == 'RegionTwo':
            self.quotations.list = mock.Mock(return_value={
                "quotations": {"2017-07-10": {"details": {
                    "Object Storage": {
                        "breakdown": {
                            "REGIONONE.o1.standard": [
                                {
                                    "cost": 13.5,
                                    "quantity": 50000.0,
                                    "rate": 0.00027,
                                    "resource_id": "1",
                                    "resource_name": "my_container",
                                    "unit": "gigabyte"
                                }
                            ]
                        },
                        "total_cost": 13.5
                    },
                    "Virtual Machine": {
                        "breakdown": {
                            "REGIONONE.b1.standard": [
                                {
                                    "cost": 15.0,
                                    "quantity": 30000.0,
                                    "rate": 0.0005,
                                    "resource_id": "22",
                                    "resource_name": "new_instance",
                                    "unit": "second"
                                }
                            ]
                        },
                        "total_cost": 15.0
                    }
                }, "total_cost": 28.5}}})
        else:
            self.quotations.list = mock.Mock(return_value={
                "quotations": {"2017-07-10": {"details": {
                    "Network": {"breakdown": {"NZ.o1.standard": [
                        {"cost": 2,
                         "quantity": 200,
                         "rate": 0.01,
                         "resource_id": "8",
                         "resource_name": "my_network",
                         "unit": "hour"}]},
                        "total_cost": 2
                    },
                    "Object Storage": {"breakdown": {"NZ.o1.standard": [
                        {"cost": 13.5,
                         "quantity": 50000.0,
                         "rate": 0.00027,
                         "resource_id": "1",
                         "resource_name": "my_container",
                         "unit": "gigabyte"}]},
                        "total_cost": 13.5},
                    "Virtual Machine": {"breakdown": {
                        "REGIONONE.b1.standard": [
                            {"cost": 15.0,
                             "quantity": 30000.0,
                             "rate": 0.0005,
                             "resource_id": "2",
                             "resource_name": "my_instance",
                             "unit": "second"},
                            {"cost": 15.0,
                             "quantity": 30000.0,
                             "rate": 0.0005,
                             "resource_id": "3",
                             "resource_name": "other_instance",
                             "unit": "second"}]
                        },
                        "total_cost": 30.0
                    }
                }, "total_cost": 45.5
                }}
            })
        self.invoices = mock.MagicMock()
        self.invoices.list = mock.Mock(return_value={
            "end": "2017-07-10 21:26:53.699730",
            "invoices": {
                "2016-08-31": {
                    "total_cost": 689.0,
                    "breakdown":{},
                },
                "2016-09-30": {
                    "total_cost": 653.0
                },
                "2017-03-31": {
                    "total_cost": 617.0
                }
            },
            "project_id": "093551df28e545eba9ba676dbd56bfa7",
            "project_name": "default_project",
            "start": "2016-07-01 00:00:00"
            })


@freeze_time("2017-07-10")
@mock.patch('distil_ui.api.distil_v2.distilclient', FakeDistilClient)
@mock.patch('openstack_dashboard.api.keystone.keystoneclient',
            get_fake_keystoneclient)
class V2BillingTests(test.TestCase):
    """Ensure the V2 api changes work. """
    def setUp(self):
        super(V2BillingTests, self).setUp()
        region_list[:] = []
        region_list.append(regionOne)

    def test_get_cost(self):
        # Test get all of the cost back from invoices
        response = distil_v2.get_cost(mock.MagicMock(name="death"))

        history = response[0]
        self.assertEqual(history[11], 0)
        self.assertEqual(history[0], 689.0)
        self.assertEqual(history[1], 653.0)
        self.assertEqual(history[5], 0)

    def test_get_month_cost_one_region(self):
        request = mock.MagicMock()
        response = distil_v2.get_cost(request)
        self.assertEqual(response[0][11], 43.5)
        self.assertEqual(
            len(response[1]), 3)
        self.assertTrue(isinstance(list(response[1])[0], distil_v2.BILLITEM))

        response_as_dict = [
            {'count': item.count, 'cost': item.cost,
             'resource': item.resource} for item in response[1]]
        self.assertIn({'resource': 'Virtual Machine', 'count': 2,
                       'cost': 30}, response_as_dict)
        self.assertIn({'resource': 'Object Storage', 'count': 1,
                       'cost': 13.5}, response_as_dict)

        self.assertIn({'resource': 'Network', 'count': 1,
                       'cost': 0}, response_as_dict)

        self.assertEqual(
            response[2].get('Virtual Machine'),
            [{"resource_name": "my_instance", "resource_id": "2",
              "region": "RegionOne", "rate": 0.0005, "cost": 15.0,
              "unit": "second", "quantity": 30000.0},
             {"resource_name": "other_instance", "resource_id": "3",
              "region": "RegionOne", "rate": 0.0005, "cost": 15.0,
              "unit": "second", "quantity": 30000.0}])

    def test_apply_discount_over(self):
        # There are 3 scenarios for current month.
        # Free hours = 216
        # In this case the available discount is more than the use
        cost = [31,
                {'Virtual Machine': distil_v2.BILLITEM(
                    id=1, resource='Virtual Machine', count=9, cost=30),
                 'Network': distil_v2.BILLITEM(
                    id=2, resource=u'Network', count=1, cost=2),
                 'Router': distil_v2.BILLITEM(
                    id=3, resource=u'Router', count=2, cost=0.5)},
                {"Virtual Machine": [
                    {"resource_name": "my_instance", "resource_id": "2",
                     "region": "RegionOne", "rate": 0.0005, "cost": 15.0,
                     "unit": "second", "quantity": 30000.0}],
                 "Network": [
                     {"resource_name": "network1", "resource_id": "8",
                      "region": "RegionOne", "rate": 0.01, "cost": 2,
                      "unit": "hour", "quantity": 200.0}],
                 "Router": [
                     {"resource_name": "router1", "resource_id": "7",
                      "region": "RegionOne", "rate": 0.0025, "cost": 0.1875,
                      "unit": "hour", "quantity": 75.0},
                     {"resource_name": "router2", "resource_id": "9",
                      "region": "RegionTwo", "rate": 0.0025, "cost": 0.3125,
                      "unit": "hour", "quantity": 125.0}]}]

        cost_after_discount = distil_v2._apply_discount(cost)

        self.assertEqual(31 - 2 - 0.5,
                         cost_after_discount[0])

        self.assertEqual(distil_v2.BILLITEM(id=2, resource=u'Network', count=1,
                                            cost=0),
                         cost_after_discount[1]['Network'])
        self.assertEqual(distil_v2.BILLITEM(id=3, resource=u'Router', count=2,
                                            cost=0),
                         cost_after_discount[1]['Router'])
        # Check that the extra line is added to the end
        self.assertEqual(
            cost_after_discount[2]['Router'],
            [{"resource_name": "router1", "resource_id": "7",
              "region": "RegionOne", "rate": 0.0025, "cost": 0.1875,
              "unit": "hour", "quantity": 75.0},
             {"resource_name": "router2", "resource_id": "9",
              "region": "RegionTwo", "rate": 0.0025, "cost": 0.3125,
              "unit": "hour", "quantity": 125.0},
             {"resource_name": "Free Router Discount", "resource_id": "",
              "region": "All Regions", "rate": -0.0025, "cost": -0.5,
              "unit": "hour", "quantity": 200}])
        self.assertEqual(
            cost_after_discount[2]['Network'],
            [{"resource_name": "network1", "resource_id": "8",
              "region": "RegionOne", "rate": 0.01, "cost": 2,
              "unit": "hour", "quantity": 200.0},
             {"resource_name": "Free Network Discount", "resource_id": "",
              "region": "All Regions", "rate": -0.01, "cost": -2,
              "unit": "hour", "quantity": 200}])

    def test_apply_discount_under(self):
        # Free hours = 216
        # In this case the available discount is lower than the use for
        # networks but the same as the use for routers
        cost = [33.54,
                {'Virtual Machine': distil_v2.BILLITEM(
                    id=1, resource='Virtual Machine', count=9, cost=30),
                 'Network': distil_v2.BILLITEM(
                    id=2, resource=u'Network', count=1, cost=3),
                 'Router': distil_v2.BILLITEM(
                    id=3, resource=u'Router', count=2, cost=0.54)},
                {"Network": [
                    {"resource_name": "network1", "resource_id": "8",
                     "region": "RegionOne", "rate": 0.01, "cost": 3,
                     "unit": "hour", "quantity": 300.0}],
                 "Router": [
                    {"resource_name": "router1", "resource_id": "7",
                     "region": "RegionOne", "rate": 0.0025, "cost": 0.25,
                     "unit": "hour", "quantity": 100.0},
                    {"resource_name": "router2", "resource_id": "9",
                     "region": "RegionTwo", "rate": 0.0025, "cost": 0.29,
                     "unit": "hour", "quantity": 116.0}]}]

        free_hours = 216

        cost_after_discount = distil_v2._apply_discount(cost)

        free_network_cost = 0.01 * free_hours
        free_router_cost = 0.0025 * free_hours

        self.assertEqual(33.54 - free_network_cost - free_router_cost,
                         cost_after_discount[0])

        self.assertIn(distil_v2.BILLITEM(id=2, resource=u'Network', count=1,
                                         cost=0.84),
                      cost_after_discount[1].values())
        self.assertIn(distil_v2.BILLITEM(id=3, resource=u'Router', count=2,
                                         cost=0.0),
                      cost_after_discount[1].values())
        # Check that the extra line is added to the end

    def test_remove_multi_region_excess(self):
        """Ensure removal of extra Object Storage cost in multi-region """

        cost = [43,
                {'Compute': distil_v2.BILLITEM(id=1, resource='Compute',
                                               count=1, cost=31),
                 'Object Storage': distil_v2.BILLITEM(
                    id=6, count=1, cost=6.0, resource='Object Storage')},
                {'Virtual Machine': [],
                 'Object Storage': []}]

        response = distil_v2._remove_excess_object_cost(cost, 2)

        self.assertEqual(response[0], 37)

    def test_multi_region_quotation(self):
        regionTwo = mock.Mock()
        regionTwo.id = 'RegionTwo'
        region_list.append(regionTwo)

        response = distil_v2.get_cost(mock.MagicMock())

        self.assertEqual(response[0][11], 58.5)
        self.assertEqual(len(response[2]['Object Storage']), 1)
