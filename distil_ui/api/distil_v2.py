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
import six
import time

from django.conf import settings

from openstack_dashboard.api import base
from openstack_dashboard.api import keystone

LOG = logging.getLogger(__name__)


COMPUTE_CATEGORY = "Compute"
NETWORK_CATEGORY = "Network"
BLOCKSTORAGE_CATEGORY = "Block Storage"
OBJECTSTORAGE_CATEGORY = "Object Storage"
DISCOUNTS_CATEGORY = "Discounts"


def distilclient(request, region_id=None):
    try:
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


def _deduplicate_objectstorage(current_details, count_regions):
    # TODO(flwang): Instead of using o1.standard, we need a better way to get
    # those product names.
    repeated_regions = count_regions - 1
    object_details = [r for r in current_details['details']
                      if r['product'].endswith('o1.standard')]
    if object_details:
        current_details[0] -= object_details.cost * repeated_regions
    return current_details


def _apply_discount(current_details):
    today = datetime.datetime.today()
    end = time.mktime(today.timetuple())
    start = time.mktime(
        datetime.datetime(today.year, today.month, 1).timetuple())
    free_network_hours = free_router_hours = math.floor((end - start) / 3600)

    # TODO(flwang): Extract the common logic for network and router as a func
    router_details = [r for r in current_details['details']
                      if r['product'].endswith('n1.router')]
    if router_details:
        rate = -router_details[0]['rate']
        product = router_details[0]['product']
        free_router_cost = round(rate * free_router_hours, 3)
        total_router_cost = sum([r['cost'] for r in router_details])
        if total_router_cost <= abs(free_router_cost):
            free_router_cost = -router_details.cost
            free_router_hours = round(free_router_cost/rate)

        current_details['details'].append(
            {'product': product,
             'resource_name': 'Free Router Tier',
             'rate': rate,
             'quantity': free_router_hours,
             'resource_id': '',
             'unit': 'Hour(s)',
             'cost': free_router_cost})

    network_details = [r for r in current_details['details']
                       if r['product'].endswith('n1.network')]
    if network_details:
        rate = -network_details[0]['rate']
        product = router_details[0]['product']
        free_network_cost = round(rate * free_network_hours, 3)
        total_network_cost = sum([r['cost'] for r in network_details])
        if total_network_cost <= abs(free_network_cost):
            free_network_cost = -network_details.cost
            free_network_hours = round(free_network_cost/rate)

        current_details['details'].append(
            {'product': product,
             'resource_name': 'Free Network Tier',
             'rate': rate,
             'quantity': free_network_hours,
             'resource_id': '',
             'unit': 'Hour(s)',
             'cost': free_network_cost})

    return current_details


def _wash_details(current_details):
    """This function is used to appy the discount for current month quotation
    and merge the cost of object storage. Unfortunately, we have to put it
    here, though here is not the right place.

    NOTE: Most of the code grab from internal billing script to keep the max
    consistency.

    :param current_details: The original cost details merged from all regions
    :return current_details: cost details after applying discount and merging
                             the object storage cost.
    """

    end = datetime.datetime.utcnow()
    start = datetime.datetime.strptime('%s-%s-01T00:00:00' %
                                       (end.year, end.month),
                                       '%Y-%m-%dT00:00:00')

    free_hours = int((end - start).total_seconds() / 3600)

    network_hours = collections.defaultdict(float)
    router_hours = collections.defaultdict(float)
    swift_usage = collections.defaultdict(list)
    washed_details = []
    rate_router = 0
    rate_network = 0

    for u in current_details["details"]:
        region = u["product"][:8]
        if u['product'].endswith('n1.network'):
            network_hours[region] += u['quantity']
            rate_network = u['rate']

        if u['product'].endswith('n1.router'):
            router_hours[region] += u['quantity']
            rate_router = u['rate']

        if u['product'].endswith('o1.standard'):
            swift_usage[u['resource_id']].append(u)
        else:
            washed_details.append(u)

    free_network_hours_left = free_hours
    for region, hours in six.iteritems(network_hours):
        free_network_hours = (hours if hours <= free_network_hours_left
                              else free_network_hours_left)
        if not free_network_hours:
            break
        line_name = 'Free Network Tier in %s' % region
        washed_details.append({'product': region + '.n1.network',
                               'resource_name': line_name,
                               'quantity': free_network_hours,
                               'resource_id': '',
                               'unit': 'Hour(s)', 'rate': -rate_network,
                               'cost': round(free_network_hours *
                                             -rate_network, 2)})
        free_network_hours_left -= free_network_hours

    free_router_hours_left = free_hours
    for region, hours in six.iteritems(router_hours):
        free_router_hours = (hours if hours <= free_router_hours_left
                             else free_router_hours_left)
        if not free_router_hours:
            break
        line_name = 'Free Router Tier in %s' % region
        washed_details.append({'product': region + '.n1.router',
                               'resource_name': line_name,
                               'quantity': free_router_hours,
                               'resource_id': '',
                               'unit': 'Hour(s)', 'rate': -rate_router,
                               'cost': round(free_router_hours *
                                             -rate_router, 2)})
        free_router_hours_left -= free_router_hours

    for container, container_usage in swift_usage.items():
        if (len(container_usage) > 0 and
            container_usage[0]['product'].endswith('o1.standard')):
            # NOTE(flwang): Find the biggest size
            container_usage[0]['prodcut'] = "NZ.o1.standard"
            container_usage[0]['quantity'] = max([u['quantity']
                                                  for u in container_usage])
            washed_details.append(container_usage[0])

    current_details["details"] = washed_details
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
        if category != DISCOUNTS_CATEGORY:
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
    identity = keystone.keystoneclient(request)
    regions = [r.id for r in identity.regions.list()]

    merged_quotations = {"total_cost": 0, "breakdown": {}, "details": [],
                         "date": today_date, "status": None}
    for region in regions:
        region_client = distilclient(request, region_id=region)
        resp = region_client.quotations.list(detailed=True)
        quotation = resp['quotations'][today_date]
        merged_quotations = _parse_quotation(quotation, merged_quotations,
                                             region)

    merged_quotations = _wash_details(merged_quotations)
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
    # NOTE(flwang): It's OK to get invoice using the 1st day of curent month
    # as the "end" date.
    end = datetime.datetime(today.year, today.month, 1)
    # FIXME(flwang): Get the last 11 invoices. If "today" is the early of month
    # then it's possible that the invoice hasn't been created. And there is no
    # way to see it based on current design of Distil API.
    invoices = distil_client.invoices.list(start, end,
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
    :return dict of credits
    """
    distil_client = distil_client or distilclient(request)

    if not distil_client:
        return {}

    return  distil_client.credits.list()

