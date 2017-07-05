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

import collections
import datetime
import logging
import math
import time

from django.conf import settings

from openstack_dashboard.api import base

LOG = logging.getLogger(__name__)
BILLITEM = collections.namedtuple('BillItem',
                                  ['id', 'resource', 'count', 'cost'])

EMPTY_BREAKDOWN = [BILLITEM(id=1, resource='N/A', count=0, cost=0)]

RES_NAME_MAPPING = {'Virtual Machine': 'Compute',
                    'Volume': 'Block Storage'}

KNOWN_RESOURCE_TYPE = ['Compute', 'Block Storage', 'Network', 'Router',
                       'Image', 'Floating IP', 'Object Storage', 'VPN',
                       'Inbound International Traffic',
                       'Outbound International Traffic',
                       'Inbound National Traffic',
                       'Outbound National Traffic']

SRV_RES_MAPPING = {'m1.tiny': 'Compute',
                   'm1.small': 'Compute',
                   'm1.mini': 'Compute',
                   'm1.medium': 'Compute',
                   'c1.small': 'Compute',
                   'm1.large': 'Compute',
                   'm1.xlarge': 'Compute',
                   'c1.large': 'Compute',
                   'c1.xlarge': 'Compute',
                   'c1.xxlarge': 'Compute',
                   'm1.2xlarge': 'Compute',
                   'c1.c1r1': 'Compute',
                   'c1.c1r2': 'Compute',
                   'c1.c1r4': 'Compute',
                   'c1.c2r1': 'Compute',
                   'c1.c2r2': 'Compute',
                   'c1.c2r4': 'Compute',
                   'c1.c2r8': 'Compute',
                   'c1.c2r16': 'Compute',
                   'c1.c4r2': 'Compute',
                   'c1.c4r4': 'Compute',
                   'c1.c4r8': 'Compute',
                   'c1.c4r16': 'Compute',
                   'c1.c4r32': 'Compute',
                   'c1.c8r4': 'Compute',
                   'c1.c8r8': 'Compute',
                   'c1.c8r16': 'Compute',
                   'c1.c8r32': 'Compute',
                   'b1.standard': 'Block Storage',
                   'o1.standard': 'Object Storage',
                   'n1.ipv4': 'Floating IP',
                   'n1.network': 'Network',
                   'n1.router': 'Router',
                   'n1.vpn': 'VPN',
                   'n1.international-in': 'Inbound International Traffic',
                   'n1.international-out': 'Outbound International Traffic',
                   'n1.national-in': 'Inbound National Traffic',
                   'n1.national-out': 'Outbound National Traffic'}

TRAFFIC_MAPPING = {'n1.international-in': 'Inbound International Traffic',
                   'n1.international-out': 'Outbound International Traffic',
                   'n1.national-in': 'Inbound National Traffic',
                   'n1.national-out': 'Outbound National Traffic'}

CACHE = {}


def distilclient(request):
    from distilclient import client
    auth_url = base.url_for(request, service_type='identity')
    distil_url = base.url_for(request, service_type='rating')
    insecure = getattr(settings, 'OPENSTACK_SSL_NO_VERIFY', False)
    cacert = getattr(settings, 'OPENSTACK_SSL_CACERT', None)
    version = getattr(settings, 'DISTIL_VERSION', '2')
    distil = client.Client(distil_url=distil_url,
                           input_auth_token=request.user.token.id,
                           tenant_id=request.user.tenant_id,
                           auth_url=auth_url,
                           region_name=request.user.services_region,
                           insecure=insecure,
                           os_cacert=cacert,
                           version=version)
    distil.request = request
    return distil


def _get_cost_from_invoice(invoice_dict, current=False):
    total_cost = invoice_dict['total_cost']
    if not current:
        return total_cost, [], {}
    service_breakdown = []
    full_breakdown = []
    for name, service in invoice_dict['details'].iteritems():
        service_breakdown.append(BILLITEM(id=len(service_breakdown) + 1,
                                          resource=name,
                                          count=len(service['breakdown']),
                                          cost=service['total_cost']))

        if (current and (name == 'Network' or name == 'Router') and
                service['total_cost'] > 0):
            today = datetime.date.today()
            start = time.mktime(today)
            end = time.mktime(datetime.datetime(today.year, today.month, 1))
            # Get the integer part of the hours
            # Attempt to get the rate based upon the full breakdown
            item = service_breakdown[-1]
            rate = service['breakdown'][0]['rate']
            free_hours = math.floor((end - start) / 3600)
            free_network_cost = rate * free_hours
            free_network_cost = (item.cost if item.cost <= free_network_cost
                                 else free_network_cost)
            service_breakdown[-1] = item._replace(cost=(item.cost -
                                                        free_network_cost))
        full_breakdown += service['breakdown']

    return (total_cost, service_breakdown, full_breakdown)


def _calculate_start_date(today):
    last_year = today.year - 1 if today.month < 12 else today.year
    month = ((today.month + 1) % 12 if today.month + 1 > 12
             else today.month + 1)
    return datetime.datetime(last_year, month, 1)


def _calculate_end_date(start):
    year = start.year + 1 if start.month + 1 > 12 else start.year
    month = (start.month + 1) % 12 or 12
    return datetime.datetime(year, month, 1)


def get_cost(request, distil_client=None, enable_eventlet=True):
    """Get cost for the last 1atest 12 months include current month

    This function will return the latest 12 months cost and their breakdown
    details, which includes current month.
    """
    history_cost = [(0, EMPTY_BREAKDOWN, []) for _ in range(12)]

    distil_client = distil_client or distilclient(request)

    if not distil_client:
        return history_cost

    today = datetime.date.today()
    start = _calculate_start_date(datetime.date.today())
    end = _calculate_end_date(start)
    final_end = datetime.datetime(today.year, today.month + 1, 1)

    invoices = distil_client.invoices.list(start, final_end)['invoices']
    print(invoices)
    sorted_invocies = {}
    for invoice_date, invoice in invoices.iteritems():
        date = datetime.datetime.strptime(
            invoice_date, '%Y-%m-%d')
        sorted_invocies[(date.year, date.month)] = invoice

    # ensure we only grab the dates we are intrested in
    for i in range(11):
        month_invoice = sorted_invocies.get((end.year, end.month))
        if month_invoice:
            history_cost[i] = _get_cost_from_invoice(month_invoice)

        start = end
        end = _calculate_end_date(start)
        if end > final_end:
            break

    today_date = today.strftime("%Y-%m-%d")
    quotation = distil_client.quotations.list(
        detailed=True)['quotations'][today_date]
    history_cost[len(history_cost) - 1] = _get_cost_from_invoice(
        quotation, current=True)

    return history_cost
