#  Copyright 2017 Catalyst IT Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import six

from django.views import generic
from openstack_dashboard.api.rest import urls
from openstack_dashboard.api.rest import utils as rest_utils
from zaqar_ui.api import distil_v2


@urls.register
class Invoices(generic.View):
    """API for retrieving invoice for a single month"""
    url_regex = r'distil/invoices?start=(?P<start>[^/]+)&end=(?P<end>[^/]+)$'

    @rest_utils.ajax()
    def get(self, request, start, end):
        invoices = distil_v2.get_invoices(request, start, end)
        if len(invoices):
            return invoices[0]
        else:
            return {}


@urls.register
class Quotation(generic.View):
    """API for retrieving current month quotation"""
    url_regex = r'distil/quotations/$'

    @rest_utils.ajax()
    def get(self, request):
        return distil_v2.get_quotation(request)


@urls.register
class Credits(generic.View):
    """API for credits"""
    url_regex = r'distil/credits/$'

    @rest_utils.ajax()
    def get(self, request):
        """Get a list of the credits for current project.

        The returned result is an object with property 'items' and each
        item under this is a credit record.
        """
        return distil_v2.get_credits(request)
