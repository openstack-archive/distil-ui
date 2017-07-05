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
from openstack_dashboard.api import keystone

LOG = logging.getLogger(__name__)


def distilclient(request, region_id=None):
    try:
        region_id = "RegionOne"
        from distilclient import client
        auth_url = base.url_for(request, service_type='identity')
        distil_url = base.url_for(request, service_type='ratingv2',
                                  region=region_id)
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
    except Exception as e:
        LOG.error(e)
        return
    return distil


def _deduplicate_objectstorage(current_details, no_regions):
    # ensure that object storage is only counted once in the total cost
    repeated_regions = no_regions - 1
    object_details = current_details[1].get(
        'Object Storage')
    if object_details:
        current_details[0] -= object_details.cost * repeated_regions
    return current_details


def _apply_discount(current_details):
    today = datetime.datetime.today()
    end = time.mktime(today.timetuple())
    start = time.mktime(
        datetime.datetime(today.year, today.month, 1).timetuple())
    free_net_hours = free_router_hours = math.floor((end - start) / 3600)

    # Apply network and router discount
    router_details = current_details[1].get('Router')
    if router_details:
        rate = -current_details[2]['Router'][0]['rate']
        free_router_cost = round(rate * free_router_hours, 3)
        if router_details.cost <= abs(free_router_cost):
            free_router_cost = -router_details.cost
            free_router_hours = round(free_router_cost/rate)

        # Remove cost from totals
        current_details[1]['Router'] = router_details._replace(
            cost=round(router_details.cost + free_router_cost, 2))
        current_details[0] += free_router_cost
        # Add discount to the details
        rate = current_details[2]['Router'].append(
            {'resource_name': 'Free Router Discount',
             'rate': rate,
             'region': 'All Regions',
             'quantity': free_router_hours,
             'resource_id': '',
             'unit': 'hour',
             'cost': free_router_cost})

    network_details = current_details[1].get('Network')
    if network_details:
        rate = -current_details[2]['Network'][0]['rate']
        free_network_cost = round(rate * free_net_hours, 3)
        if abs(free_network_cost) >= network_details.cost:
            free_network_cost = -network_details.cost
            free_net_hours = round(free_network_cost/rate)
        # Remove cost from totals
        current_details[1]['Network'] = network_details._replace(
            cost=round(network_details.cost + free_network_cost, 2))
        current_details[0] += free_network_cost
        # Add discount to the details
        rate = current_details[2]['Network'].append(
            {'resource_name': 'Free Network Discount',
             'rate': rate,
             'region': 'All Regions',
             'quantity': free_net_hours,
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


def _parse_invoice(invoice):
    parsed = {"total_cost": 0, "breakdown": {}, "details": []}
    parsed["total_cost"] += invoice["total_cost"]
    breakdown = parsed["breakdown"]
    details = parsed["details"]
    for category, services in invoice['details'].items():
        breakdown[category] = services["total_cost"]
        for product in services["breakdown"]:
            for order_line in services["breakdown"][product]:
                 order_line["product"] = product 
                 details.append(order_line)
    return parsed


def _parse_quotation(quotation, merged_quotations, region=None):
    parsed = merged_quotations
    parsed["total_cost"] += quotation["total_cost"]
    breakdown = parsed["breakdown"]
    details = parsed["details"]
    for category, services in quotation['details'].items():
        breakdown[category] = services["total_cost"]
        for product in services["breakdown"]:
            for order_line in services["breakdown"][product]:
                 order_line["product"] = product 
                 details.append(order_line)

    return parsed

def _get_quotations(request):
    today_date = datetime.date.today().strftime("%Y-%m-%d")
    #identity = keystone.keystoneclient(request)
    #regions = [r.id for r in identity.regions.list()]
    regions = ["nz-hlz-1", "nz-por-1", "nz_wlg_2"]

    merged_quotations = {"total_cost": 0, "breakdown": {}, "details": [],
                         "date": today_date, "status": None}
    for region in regions:
        region_client = distilclient(request, region_id=region)
        quotation = region_client.quotations.list(detailed=True)['quotations'][today_date]
        merged_quotations = _parse_quotation(quotation, merged_quotations,
                                             region)

    #merged_quotations = _apply_discount(merged_quotations)
    #merged_quotations = _deduplicate_objectstorage(merged_quotations, len(regions))
    return merged_quotations


def get_cost(request, distil_client=None):
    """Get cost for the 1atest 12 months include current month

    This function will return the latest 12 months cost and the breakdown
    details for the each month.
    :param request: Horizon request object
    :param distil_client: Client object of Distilclient
    :return list of cost for last 12 months
    """
    cost = [{"date": None, "total_cost": 0, "paid": True, "breakdown": {},
             "details": {}} for _ in range(12)]
    distil_client = distil_client or distilclient(request)
    if not distil_client:
        return cost

    # 1. Process invoices
    today = datetime.date.today()
    start = _calculate_start_date(datetime.date.today())
    end = _calculate_end_date(start)
    final_end = datetime.datetime(today.year, today.month + 1, 1)
    # TODO(flwang): Get the last 11 invoices. If "today" is the early of month
    # then it's possible that the invoice hasn't been created. And there is no
    # way to see it based on current design of Distil API.
    invoices = distil_client.invoices.list(start, final_end,
                                           detailed=True)['invoices']
    ordered_invoices = collections.OrderedDict(sorted(invoices.items(),
                                              key=lambda t: t[0]))
    # NOTE(flwang): The length of invoices dict could be less than 11 based on
    # above comments.
    for i in range(len(ordered_invoices)):
        cost[i]["date"] = ordered_invoices.keys()[i]
        cost[i]["total_cost"] = ordered_invoices.values()[i]["total_cost"]
        cost[i]["status"] = ordered_invoices.values()[i].get("status", None)
        parsed = _parse_invoice(ordered_invoices.values()[i])
        cost[i]["breakdown"] = parsed["breakdown"]
        cost[i]["details"] = parsed["details"]

    # 2. Process quotations from all regions
    # NOTE(flwang): The quotations from all regions is always the last one of
    # the cost list.
    cost[-1] = _get_quotations(request)

    return cost


def get_credits(request, distil_client=None):
    """Get balance of customer's credit. For now, it only supports credits like
    trail, development grant or education grant. In the future, we will add
    supports for term discount if it applys.

    :param request: Horizon request object
    :param distil_client: Client object of Distilclient
    :return 
    """
    distil_client = distil_client or distilclient(request)

    if not distil_client:
        return {}

    return  distil_client.credits.list()
