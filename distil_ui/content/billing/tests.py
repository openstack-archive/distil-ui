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

import collections
import datetime
import mock
from mox3 import mox

from distil_ui.content.billing import base
from distil_ui.content.billing import views
from django.utils import timezone
from horizon import forms
from openstack_dashboard.test import helpers as test

BILLITEM = collections.namedtuple('BillItem',
                                  ['id', 'resource', 'count', 'cost'])


class FakeUser(object):
    roles = [{'name': 'admin'}]
    authorized_tenants = ["tenant_name"]

    def is_authenticated(self):
        return True


class FakeRequest(object):
    def _get(x, y):
        if x == 'format' and y == 'html':
            return 'csv'
        return None

    def is_ajax(self):
        return False

    user = FakeUser()
    session = mock.MagicMock()
    GET = mock.MagicMock()
    GET.get = _get


class BaseBillingTests(test.TestCase):
    """FIXME(flwang): Move this test to rest_api_tests.py

    Now we're putting the api test at here, since we don't want to hack
    horizon too much. That means we don't want to put the api.py under /api
    folder, at least for now.
    """

    def setUp(self):
        super(BaseBillingTests, self).setUp()
        self.mocker = mox.Mox()
        self.billing = base.BaseBilling(FakeRequest(), 'my_project_id')
        self.year = 2017
        self.month = 1
        self.day = 30

    def test_today(self):
        delta = datetime.timedelta(seconds=1)
        self.assertTrue(self.billing.today - timezone.now() < delta)

    def test_get_start(self):
        start = datetime.datetime(self.year, self.month, self.day, 0, 0, 0)
        self.assertEqual(self.billing.get_start(self.year, self.month,
                                                self.day),
                         timezone.make_aware(start, timezone.utc))

    def test_get_end(self):
        end = datetime.datetime(self.year, self.month, self.day, 23, 59, 59)
        self.assertEqual(self.billing.get_end(self.year, self.month, self.day),
                         timezone.make_aware(end, timezone.utc))

    def test_get_date_range(self):
        args_start = (self.billing.today.year, self.billing.today.month, 1)
        args_end = (self.billing.today.year, self.billing.today.month,
                    self.billing.today.day)
        start = self.billing.get_start(*args_start)
        end = self.billing.get_end(*args_end)
        self.assertEqual(self.billing.get_date_range(),
                         (start, end))

    @mock.patch('distil_ui.content.billing.base.BaseBilling.get_form')
    def test_get_date_range_valid_form(self, mock_get_form):
        start = datetime.datetime(self.year, self.month, self.day, 0, 0, 0)
        end = datetime.datetime(self.year, self.month, self.day, 23, 59, 59)
        myform = forms.DateForm({'start': start, 'end': end})
        myform.data = {'start': start, 'end': end}
        myform.cleaned_data = {'start': start, 'end': end}
        mock_get_form.return_value = myform
        self.assertEqual(self.billing.get_date_range(),
                         (timezone.make_aware(start, timezone.utc),
                          timezone.make_aware(end, timezone.utc)))

    def test_init_form(self):
        start = datetime.date(self.billing.today.year,
                              self.billing.today.month, 1)
        end = datetime.date.today()
        self.assertEqual(self.billing.init_form(), (start, end))

    def test_get_form(self):
        start = datetime.date(self.billing.today.year,
                              self.billing.today.month, 1).strftime("%Y-%m-%d")
        end = datetime.date.today().strftime("%Y-%m-%d")
        self.assertEqual(self.billing.get_form().initial,
                         {"start": start, "end": end})

    def test_get_billing_list(self):
        self.assertEqual(self.billing.get_billing_list(None, None), [])


class ViewsTests(test.TestCase):
    def setUp(self):
        super(ViewsTests, self).setUp()
        project_id = "fake_project_id"
        self.view = views.IndexView()
        self.view.request = FakeRequest()
        self.view.billing = base.BaseBilling(self.request, project_id)

    @mock.patch('horizon.tables.DataTableView.get_context_data')
    def test_get_context_data(self, mock_get_context_data):
        # TODO(flwang): Will add in next patch
        pass
