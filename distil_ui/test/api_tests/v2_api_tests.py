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

import datetime

import mock

from distil_ui.api import distil_v2
from freezegun import freeze_time
from openstack_dashboard.test import helpers as test

regionOne = mock.Mock(id='RegionOne')
regionTwo = mock.Mock(id='RegionTwo')
region_list = [regionOne, regionTwo]
fake_keystoneclient = mock.MagicMock()
fake_keystoneclient.regions.list = mock.Mock(return_value=region_list)
get_fake_keystoneclient = mock.Mock(return_value=fake_keystoneclient)


class FakeUser(object):
    roles = [{'name': 'admin'}]
    token = mock.MagicMock()
    tenant_id = "fake"
    services_region = "fake"


class FakeRequest(object):
    user = FakeUser()


class FakeDistilClient(mock.MagicMock):
    def __init__(self, *args, **kwargs):
        super(FakeDistilClient, self).__init__(*args, **kwargs)
        self.region_id = kwargs.get('region_id')
        self.quotations = mock.MagicMock()
        if self.region_id == 'RegionOne':
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
                            "REGIONTWO.b1.standard": [
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
        elif self.region_id == 'RegionTwo':
            self.quotations.list = mock.Mock(return_value={
                "quotations": {"2017-07-10": {"details": {
                    "Network": {"breakdown": {"REGIONONE.b1.standard": [
                        {"cost": 2,
                         "quantity": 200,
                         "rate": 0.01,
                         "resource_id": "8",
                         "resource_name": "my_block",
                         "unit": "hour"}]},
                        "total_cost": 2
                    },
                    "Object Storage": {"breakdown": {"REGIONTWO.o1.standard": [
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
            "start": "2016-08-31 00:00:00",
            "end": "2017-07-01 00:00:00",
            "invoices": {
                "2017-06-30": {
                    "total_cost": 689.0,
                    "status": "paid",
                    "details": {'Compute': {'total_cost': 767.06, 'breakdown':
                                            {'NZ-POR-1.c1.c4r8': [{'rate': 0.248, 'resource_name': 'postgresql', 'cost': 184.51, 'unit': 'Hour(s)', 'quantity': 744.0}],  # noqa
                                             'NZ-POR-1.c1.c8r32': [{'rate': 0.783, 'resource_name': 'docker', 'cost': 582.55, 'unit': 'Hour(s)', 'quantity': 744.0}]}   # noqa
                                            }
                                }
                },
                "2017-05-31": {
                    "total_cost": 653.0,
                    "status": "paid",
                    "details": {'Block Storage': {'total_cost': 75.88,
                                                  'breakdown': {'NZ-POR-1.b1.standard': [{'rate': 0.0005, 'resource_name': 'docker - root disk', 'cost': 3.72, 'unit': 'Gigabyte-hour(s)', 'quantity': 7440.0}, {'rate': 0.0005, 'resource_name': 'docker_tmp', 'cost': 11.9, 'unit': 'Gigabyte-hour(s)', 'quantity': 23808.0},   # noqa
                                                                                         {'rate': 0.0005, 'resource_name': 'postgresql - root disk', 'cost': 3.72, 'unit': 'Gigabyte-hour(s)', 'quantity': 7440.0}, {'rate': 0.0005, 'resource_name': 'dbserver_dbvol', 'cost': 7.44, 'unit': 'Gigabyte-hour(s)', 'quantity': 14880.0},   # noqa
                                                                                         {'rate': 0.0005, 'resource_name': 'server_dockervol', 'cost': 18.6, 'unit': 'Gigabyte-hour(s)', 'quantity': 37200.0}, {'rate': 0.0005, 'resource_name': 'docker_uservol', 'cost': 18.6, 'unit': 'Gigabyte-hour(s)', 'quantity': 37200.0},   # noqa
                                                                                         {'rate': 0.0005, 'resource_name': 'docker_swap', 'cost': 11.9, 'unit': 'Gigabyte-hour(s)', 'quantity': 23808.0}]}},   # noqa
                                }
                },
                "2017-04-30": {"total_cost": 0, "details": {}},
                "2017-03-31": {"total_cost": 0, "details": {}},
                "2017-02-28": {"total_cost": 0, "details": {}},
                "2017-01-31": {"total_cost": 0, "details": {}},
                "2016-12-31": {"total_cost": 0, "details": {}},
                "2016-11-30": {"total_cost": 0, "details": {}},
                "2016-10-31": {"total_cost": 0, "details": {}},
                "2016-09-30": {"total_cost": 0, "details": {}},
                "2016-08-31": {
                    "total_cost": 617.0,
                    "status": "open",
                    "details": {'Network': {'total_cost': 9.64,
                                            'breakdown': {'NZ-POR-1.n1.ipv4': [{'rate': 0.006, 'resource_name': '150.242.40.138', 'cost': 4.46, 'unit': 'Hour(s)', 'quantity': 744.0}, {'rate': 0.006, 'resource_name': '150.242.40.139', 'cost': 4.46, 'unit': 'Hour(s)', 'quantity': 744.0}]}}   # noqa
                                }
                }
            },
            "project_id": "093551df28e545eba9ba676dbd56bfa7",
            "project_name": "default_project",
            })

        self.credits = mock.MagicMock()
        self.credits.list = mock.Mock(return_value={'credits': [{'code': 'abcdefg', 'type': 'Cloud Trial Credit', 'expiry_date': '2017-09-30', 'balance': 300.0, 'recurring': False, 'start_date': '2017-08-02 22:16:28'}]})  # noqa


@mock.patch('distil_ui.api.distil_v2.distilclient', FakeDistilClient)
class V2BillingTests(test.TestCase):
    """Ensure the V2 api changes work. """
    def setUp(self):
        super(V2BillingTests, self).setUp()
        region_list[:] = []
        region_list.append(regionOne)
        region_list.append(regionTwo)

    @mock.patch("openstack_dashboard.api.base.url_for")
    def test_init_distilclient(self, mock_url_for):
        request = FakeRequest()
        distilclient = distil_v2.distilclient(request)
        self.assertIsNotNone(distilclient)

    def test_calculate_start_date(self):
        today = datetime.date(2017, 1, 1)
        start = distil_v2._calculate_start_date(today)
        self.assertEqual((start.year, start.month, start.day), (2016, 2, 1))

        today = datetime.date(2017, 7, 1)
        start = distil_v2._calculate_start_date(today)
        self.assertEqual((start.year, start.month, start.day), (2016, 8, 1))

        today = datetime.date(2017, 12, 31)
        start = distil_v2._calculate_start_date(today)
        self.assertEqual((start.year, start.month, start.day), (2017, 1, 1))

    def test_calculate_end_date(self):
        start = datetime.date(2015, 1, 1)
        end = distil_v2._calculate_end_date(start)
        self.assertEqual((end.year, end.month, end.day), (2015, 2, 1))

        start = datetime.date(2015, 6, 6)
        end = distil_v2._calculate_end_date(start)
        self.assertEqual((end.year, end.month, end.day), (2015, 7, 1))

        start = datetime.date(2015, 12, 31)
        end = distil_v2._calculate_end_date(start)
        self.assertEqual((end.year, end.month, end.day), (2016, 1, 1))

    @freeze_time("2017-07-10")
    @mock.patch('openstack_dashboard.api.keystone.keystoneclient',
                get_fake_keystoneclient)
    def test_get_cost(self):
        cost = distil_v2.get_cost(mock.MagicMock())

        self.assertEqual(cost[11]["total_cost"], 60.5)
        self.assertEqual(cost[10]["total_cost"], 689.0)
        self.assertEqual(cost[9]["total_cost"], 653.0)
        self.assertEqual(cost[8]["total_cost"], 0)
        self.assertEqual(cost[0]["total_cost"], 617)

    def test_get_credit(self):
        credits = distil_v2.get_credits(mock.MagicMock())
        expect = {'credits': [{'code': 'abcdefg',
                               'type': 'Cloud Trial Credit',
                               'expiry_date': '2017-09-30',
                               'balance': 300.0,
                               'recurring': False,
                               'start_date': '2017-08-02 22:16:28'}]}

        self.assertDictEqual(credits, expect)
