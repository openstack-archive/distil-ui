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
                    "status": "paid",
                    "details": {'Compute': {'total_cost': 767.06, 'breakdown':
                                            {'NZ-POR-1.c1.c4r8': [{'rate': 0.248, 'resource_name': 'postgresql', 'cost': 184.51, 'unit': 'Hour(s)', 'quantity': 744.0}],  # noqa
                                             'NZ-POR-1.c1.c8r32': [{'rate': 0.783, 'resource_name': 'docker', 'cost': 582.55, 'unit': 'Hour(s)', 'quantity': 744.0}]}   # noqa
                                            }
                                }
                },
                "2016-09-30": {
                    "total_cost": 653.0,
                    "status": "paid",
                    "details": {'Block Storage': {'total_cost': 75.88,
                                                  'breakdown': {'NZ-POR-1.b1.standard': [{'rate': 0.0005, 'resource_name': 'docker - root disk', 'cost': 3.72, 'unit': 'Gigabyte-hour(s)', 'quantity': 7440.0}, {'rate': 0.0005, 'resource_name': 'docker_tmp', 'cost': 11.9, 'unit': 'Gigabyte-hour(s)', 'quantity': 23808.0},   # noqa
                                                                                         {'rate': 0.0005, 'resource_name': 'postgresql - root disk', 'cost': 3.72, 'unit': 'Gigabyte-hour(s)', 'quantity': 7440.0}, {'rate': 0.0005, 'resource_name': 'dbserver_dbvol', 'cost': 7.44, 'unit': 'Gigabyte-hour(s)', 'quantity': 14880.0},   # noqa
                                                                                         {'rate': 0.0005, 'resource_name': 'server_dockervol', 'cost': 18.6, 'unit': 'Gigabyte-hour(s)', 'quantity': 37200.0}, {'rate': 0.0005, 'resource_name': 'docker_uservol', 'cost': 18.6, 'unit': 'Gigabyte-hour(s)', 'quantity': 37200.0},   # noqa
                                                                                         {'rate': 0.0005, 'resource_name': 'docker_swap', 'cost': 11.9, 'unit': 'Gigabyte-hour(s)', 'quantity': 23808.0}]}},   # noqa
                                }
                },
                "2017-03-31": {
                    "total_cost": 617.0,
                    "status": "open",
                    "details": {'Network': {'total_cost': 9.64,
                                            'breakdown': {'NZ-POR-1.n1.ipv4': [{'rate': 0.006, 'resource_name': '150.242.40.138', 'cost': 4.46, 'unit': 'Hour(s)', 'quantity': 744.0}, {'rate': 0.006, 'resource_name': '150.242.40.139', 'cost': 4.46, 'unit': 'Hour(s)', 'quantity': 744.0}]}}   # noqa
                                }
                }
            },
            "project_id": "093551df28e545eba9ba676dbd56bfa7",
            "project_name": "default_project",
            "start": "2016-07-01 00:00:00"
            })

        self.credits = mock.MagicMock()
        self.credits.list = mock.Mock(return_value={})


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
        cost = distil_v2.get_cost(mock.MagicMock(name="death"))

        self.assertEqual(cost[11]["total_cost"], 45.5)
        self.assertEqual(cost[0]["total_cost"], 689.0)
        self.assertEqual(cost[1]["total_cost"], 653.0)
        self.assertEqual(cost[5]["total_cost"], 0)
