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

from openstack_dashboard.api import base, keystone

LOG = logging.getLogger(__name__)
BILLITEM = collections.namedtuple('BillItem',
                                  ['id', 'resource', 'count', 'cost'])


def distilclient(request, region_id=None):
    from distilclient import client
    auth_url = base.url_for(request, service_type='identity')
    distil_url = base.url_for(request, service_type='rating', region=region_id)
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


def _get_cost_from_invoice(invoice_dict, current_details=None, region=None):
    if not current_details:
        current_details = [0, {}, collections.defaultdict(list)]
    current_details[0] += invoice_dict['total_cost']

    service_breakdown = current_details[1]
    full_breakdown = current_details[2]
    for name, service in invoice_dict['details'].iteritems():
        if name != 'Object Storage' or not full_breakdown[name]:
            bill = service_breakdown.get(name)
            if not bill:
                bill = BILLITEM(id=len(service_breakdown) + 1,
                                resource=name,
                                count=len(service['breakdown']),
                                cost=service['total_cost'])
                service_breakdown[name] = bill
            else:
                new_bill = BILLITEM(id=bill.id,
                                    resource=name,
                                    count=(bill.count +
                                           len(service['breakdown'])),
                                    cost=bill.cost + service['total_cost'])
                service_breakdown[name] = new_bill

            for internal_service, details in service['breakdown'].iteritems():
                if name == 'Object Storage':
                    for resource in details:
                        resource['region'] = "All regions"
                else:
                    for resource in details:
                        resource['region'] = region
                full_breakdown[name] += details
    return current_details


def _remove_excess_object_cost(current_details, no_regions):
    # ensure that object storage is only counted once in the total cost
    repeated_regions = no_regions - 1
    month_excess = current_details[1].get(
        'Object Storage').cost * repeated_regions
    current_details[0] -= month_excess
    return current_details


def _apply_discount(current_details, no_regions):
    today = datetime.date.today()
    end = time.mktime(today.timetuple())
    start = time.mktime(
        datetime.datetime(today.year, today.month, 1).timetuple())
    free_hours = math.floor((end - start) / 3600)

    # Apply network and router discount
    router_details = current_details[1].get('Router')
    if router_details:
        rate = -current_details[2]['Router'][0]['rate']
        free_router_cost = rate * free_hours
        free_router_cost = (router_details.cost
                            if router_details.cost <= free_router_cost
                            else free_router_cost)
        # Remove cost from totals
        current_details[1]['Router'] = router_details._replace(
            cost=(router_details.cost + free_router_cost))
        current_details[0] += free_router_cost
        # Add discount to the details
        rate = current_details[2]['Router'].append(
            {'resouce_name': 'Free Router Discount',
             'rate': rate,
             'region': 'All Regions',
             'quantity': free_hours,
             'resource_id': '',
             'unit': 'hour',
             'cost': free_router_cost})

    network_details = current_details[1].get('Network')
    if network_details:
        rate = -current_details[2]['Network'][0]['rate']
        free_network_cost = rate * free_hours
        free_network_cost = (network_details.cost
                             if network_details.cost <= free_network_cost
                             else free_network_cost)
        # Remove cost from totals
        current_details[1]['Network'] = network_details._replace(
            cost=(network_details.cost + free_network_cost))
        current_details[0] += free_network_cost
        # Add discount to the details
        rate = current_details[2]['Network'].append(
            {'resource_name': 'Free Network Discount',
             'rate': rate,
             'region': 'All Regions',
             'quantity': free_hours,
             'resource_id': '',
             'unit': 'hour',
             'cost': free_network_cost})
    return current_details


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
    """Get cost for the 1atest 12 months include current month

    This function will return the latest 12 months cost and the breakdown
    details for the current month.
    """
    history_cost = [0 for _ in range(12)]

    distil_client = distil_client or distilclient(request)

    if not distil_client:
        return history_cost, [], {}

    today = datetime.date.today()
    start = _calculate_start_date(datetime.date.today())
    end = _calculate_end_date(start)
    final_end = datetime.datetime(today.year, today.month + 1, 1)

    invoices = distil_client.invoices.list(start, final_end)['invoices']
    sorted_invocies = {}

    for invoice_date, invoice in invoices.iteritems():
        date = datetime.datetime.strptime(
            invoice_date, '%Y-%m-%d')
        sorted_invocies[(date.year, date.month)] = invoice

    for i in range(11):
        month_invoice = sorted_invocies.get((start.year, start.month))
        if month_invoice:
            history_cost[i] = month_invoice['total_cost']

        start = end
        end = _calculate_end_date(start)
        if end > final_end:
            break

    today_date = today.strftime("%Y-%m-%d")
    region_details = [0, {}, collections.defaultdict(list)]
    identity = keystone.keystoneclient(request)
    regions = identity.regions.list()

    for region in regions:
        region_client = distilclient(request, region_id=region.id)

        quotation = region_client.quotations.list(
            detailed=True)['quotations'][today_date]
        region_details = _get_cost_from_invoice(
            quotation, region_details, region.id)

    region_details = _apply_discount(region_details, len(regions))
    history_cost[-1] = region_details[0]

    return history_cost, region_details[1].values(), region_details[2]
