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
import six

from django.conf import settings
from django.utils.html import escape

from openstack_dashboard.api import base

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


def _calculate_start_date(today):
    last_year = today.year - 1 if today.month < 12 else today.year
    month = ((today.month + 1) % 12 if today.month + 1 > 12
             else today.month + 1)
    return datetime.datetime(last_year, month, 1)


def _calculate_end_date(start):
    year = start.year + 1 if start.month + 1 > 12 else start.year
    month = (start.month + 1) % 12 or 12
    return datetime.datetime(year, month, 1)


def _wash_details(current_details):
    """Apply the discount for current month quotation and merge object storage

    Unfortunately, we have to put it here, though here is not the right place.
    Most of the code grab from internal billing script to keep the max
    consistency.
    :param current_details: The original cost details merged from all regions
    :return cost details after applying discount and merging object storage
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
        # FIXME(flwang): 8 is the magic number here, we need a better way
        # to get the region name.
        region = u["product"].split(".")[0]
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

    total_free_router_network_cost = 0
    free_network_hours_left = free_hours
    for region, hours in six.iteritems(network_hours):
        free_network_hours = (hours if hours <= free_network_hours_left
                              else free_network_hours_left)
        if not free_network_hours:
            break
        line_name = 'Free Network Tier in %s' % region
        cost = round(free_network_hours * -rate_network, 2)
        total_free_router_network_cost += cost
        washed_details.append({'product': region + '.n1.network',
                               'resource_name': line_name,
                               'quantity': free_network_hours,
                               'resource_id': '',
                               'unit': 'hour', 'rate': -rate_network,
                               'cost': cost})
        free_network_hours_left -= free_network_hours

    free_router_hours_left = free_hours
    for region, hours in six.iteritems(router_hours):
        free_router_hours = (hours if hours <= free_router_hours_left
                             else free_router_hours_left)
        if not free_router_hours:
            break
        line_name = 'Free Router Tier in %s' % region
        cost = round(free_router_hours * -rate_router, 2)
        total_free_router_network_cost += cost
        washed_details.append({'product': region + '.n1.router',
                               'resource_name': line_name,
                               'quantity': free_router_hours,
                               'resource_id': '',
                               'unit': 'hour', 'rate': -rate_router,
                               'cost': cost})
        free_router_hours_left -= free_router_hours

    region_count = 0
    for container, container_usage in swift_usage.items():
        region_count = len(container_usage)
        if (len(container_usage) > 0 and
                container_usage[0]['product'].endswith('o1.standard')):
            # NOTE(flwang): Find the biggest size
            container_usage[0]['product'] = "NZ.o1.standard"
            container_usage[0]['quantity'] = max([u['quantity']
                                                  for u in container_usage])
            washed_details.append(container_usage[0])

    current_details["details"] = washed_details
    # NOTE(flwang): Currently, the breakdown will accumulate all the object
    # storage cost, so we need to deduce the duplicated part.
    object_cost = current_details["breakdown"].get(OBJECTSTORAGE_CATEGORY, 0)

    dup_object_cost = (0 if region_count == 0 else
                       (region_count - 1) * (object_cost / region_count))
    current_details["total_cost"] = (current_details["total_cost"] -
                                     dup_object_cost)

    # NOTE(flwang): Apply the free router and network to reflect correct cost.
    # The total_free_router_network_cost is negative value.
    current_details["total_cost"] += total_free_router_network_cost
    current_details["total_cost"] = (current_details["total_cost"] if
                                     current_details["total_cost"] > 0 else 0)

    return current_details


def _parse_invoice(invoice):
    LOG.debug("Start to get invoices.")
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
                order_line["resource_name"] = escape(
                    order_line["resource_name"])
                details.append(order_line)
    LOG.debug("Got quotations successfully.")
    return parsed


def _parse_quotation(quotation, merged_quotations, region=None):
    parsed = merged_quotations
    parsed["total_cost"] += quotation["total_cost"]
    breakdown = parsed["breakdown"]
    details = parsed["details"]
    for category, services in quotation['details'].items():
        if category in breakdown:
            breakdown[category] += services["total_cost"]
        else:
            breakdown[category] = services["total_cost"]
        for product in services["breakdown"]:
            for order_line in services["breakdown"][product]:
                order_line["product"] = product
                order_line["resource_name"] = escape(
                    order_line["resource_name"])
                details.append(order_line)

    return parsed


def _get_quotations(request):
    LOG.debug("Start to get quotations from all regions.")
    today_date = datetime.date.today().strftime("%Y-%m-%d")
    regions = request.user.available_services_regions

    merged_quotations = {"total_cost": 0, "breakdown": {}, "details": [],
                         "date": today_date, "status": None}

    for region in regions:
        region_client = distilclient(request, region_id=region)
        resp = region_client.quotations.list(detailed=True)
        quotation = resp['quotations'][today_date]
        merged_quotations = _parse_quotation(quotation, merged_quotations,
                                             region)

    merged_quotations = _wash_details(merged_quotations)
    LOG.debug("Got quotations from all regions successfully.")
    return merged_quotations


def get_cost(request, distil_client=None):
    """Get cost for the 1atest 12 months include current month

    This function will return the latest 12 months cost and the breakdown
    details for the each month.
    :param request: Horizon request object
    :param distil_client: Client object of Distilclient
    :return list of cost for last 12 months
    """
    # 1. Process invoices
    today = datetime.date.today()
    start = _calculate_start_date(datetime.date.today())
    # NOTE(flwang): It's OK to get invoice using the 1st day of curent month
    # as the "end" date.
    end = datetime.datetime(today.year, today.month, 1)

    cost = [{"date": None, "total_cost": 0, "paid": False, "breakdown": {},
             "details": {}}]

    temp_end = end
    for i in range(11):
        last_day = temp_end - datetime.timedelta(seconds=1)
        temp_end = datetime.datetime(last_day.year, last_day.month, 1)
        cost.insert(0, {"date": last_day.strftime("%Y-%m-%d"), "total_cost": 0,
                        "paid": False, "breakdown": {}, "details": {}})
        if temp_end < start:
            break

    distil_client = distil_client or distilclient(request)
    if not distil_client:
        return cost
    # FIXME(flwang): Get the last 11 invoices. If "today" is the early of month
    # then it's possible that the invoice hasn't been created. And there is no
    # way to see it based on current design of Distil API.
    invoices = distil_client.invoices.list(start, end,
                                           detailed=True)['invoices']

    ordered_invoices = collections.OrderedDict(sorted(invoices.items(),
                                               key=lambda t: t[0]))
    # NOTE(flwang): The length of invoices dict could be less than 11 based on
    # above comments.
    for i in range(len(cost)):
        month_cost = ordered_invoices.get(cost[i]['date'])
        if not month_cost:
            continue
        cost[i]["total_cost"] = month_cost["total_cost"]
        cost[i]["status"] = month_cost.get("status", None)
        parsed = _parse_invoice(month_cost)
        cost[i]["breakdown"] = parsed["breakdown"]
        cost[i]["details"] = parsed["details"]

    # 2. Process quotations from all regions
    # NOTE(flwang): The quotations from all regions is always the last one of
    # the cost list.
    cost[-1] = _get_quotations(request)

    return cost


def get_credits(request, distil_client=None):
    """Get balance of customer's credit

    For now, it only supports credits like trail, development grant or
    education grant. In the future, we will add supports for term discount if
    it applys.
    :param request: Horizon request object
    :param distil_client: Client object of Distilclient
    :return dict of credits
    """
    distil_client = distil_client or distilclient(request)

    if not distil_client:
        return {}

    return distil_client.credits.list()
