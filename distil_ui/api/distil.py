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
import eventlet

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
    try:
        try:
            from distilclient import client
        except Exception:
            from distil.client import client
        auth_url = base.url_for(request, service_type='identity')
        distil_url = base.url_for(request, service_type='rating')
        insecure = getattr(settings, 'OPENSTACK_SSL_NO_VERIFY', False)
        cacert = getattr(settings, 'OPENSTACK_SSL_CACERT', None)
        distil = client.Client(distil_url=distil_url,
                               os_auth_token=request.user.token.id,
                               os_tenant_id=request.user.tenant_id,
                               os_auth_url=auth_url,
                               os_region_name=request.user.services_region,
                               insecure=insecure,
                               os_cacert=cacert)
        distil.request = request
    except Exception as e:
        LOG.error(e)
        return
    return distil


def _get_month_cost(distil_client, tenant_id, start_str, end_str,
                    history_cost, i):
    today = datetime.datetime.today()
    start = datetime.datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S')
    cache_key = (distil_client.endpoint + '_' + tenant_id + '_' +
                 start_str + '_' + end_str)
    if cache_key in CACHE:
        history_cost[i] = CACHE[cache_key]
        return

    month_cost = distil_client.get_rated([tenant_id], start_str,
                                         end_str)['usage']

    resource_cost = collections.OrderedDict()
    prices = {}
    cost_details = collections.defaultdict(list)
    for res in KNOWN_RESOURCE_TYPE:
        cost_details[res] = []

    for res_id, details in month_cost['resources'].items():
        resource_type = details['type']
        for s in details['services']:
            if resource_type not in prices:
                try:
                    prices[resource_type] = float(s.get('rate', 0))
                except Exception as e:
                    LOG.error('Failed to get rate for %s since %s' % (s, e))
            # Only collect service details for current month, we may support
            # the details for history in the future.
            if ((start.year == today.year and start.month == today.month) or
                    s['name'] in TRAFFIC_MAPPING):
                try:
                    s_copy = s.copy()
                    s_copy['volume'] = round(float(s_copy['volume']), 4)
                    s_copy['resource_id'] = res_id
                    cd_key = ('Image' if resource_type == 'Image' else
                              SRV_RES_MAPPING.get(s['name'], resource_type))
                    if cd_key in ('Image', 'Block Storage', 'Object Storage'):
                        s_copy['unit'] = 'gigabyte * hour'
                    cost_details.get(cd_key).append(s_copy)
                except Exception as e:
                    LOG.error('Failed to save: %s, since %s' % (s, e))
                    continue

        res_type = (resource_type if resource_type not in
                    RES_NAME_MAPPING else RES_NAME_MAPPING[resource_type])
        count, cost = _calculate_count_cost(list(details['services']),
                                            res_type)

        if res_type in resource_cost:
            tmp_count_cost = resource_cost[res_type]
            tmp_count_cost = [tmp_count_cost[0] + count,
                              tmp_count_cost[1] + cost]
            resource_cost[res_type] = tmp_count_cost
        else:
            resource_cost[res_type] = [count, cost]

    # NOTE(flwang): Based on current Distil API design, it's making the
    # traffic data associate with floating ip and router. So we need to
    # get them out and recalculate the cost of floating ip and router.
    if ['admin'] in [r.values() for r in distil_client.request.user.roles]:
        _calculate_traffic_cost(cost_details, resource_cost)

    breakdown = []
    total_cost = 0
    for resource, count_cost in resource_cost.items():
        rounded_cost = round(count_cost[1], 2)
        breakdown.append(BILLITEM(id=len(breakdown) + 1,
                                  resource=resource,
                                  count=count_cost[0],
                                  cost=rounded_cost))
        total_cost += rounded_cost

    if breakdown:
        if start.year == today.year and start.month == today.month:
            # Only apply/show the discount for current month
            end_str = today.strftime('%Y-%m-%dT%H:00:00')
            history_cost[i] = _apply_discount((round(total_cost, 2),
                                               breakdown, cost_details),
                                              start_str,
                                              end_str,
                                              prices)
        else:
            month_cost = (round(total_cost, 2), breakdown, [])
            if month_cost:
                CACHE[cache_key] = month_cost
            history_cost[i] = month_cost


def _calculate_count_cost(service_details, resource_type):
    count = 0
    cost = 0
    for s in service_details:
        if resource_type == 'Image' and s['name'] == 'b1.standard':
            count += 1
            cost += float(s['cost'])
        if SRV_RES_MAPPING.get(s['name'], '') == resource_type:
            count += 1
            cost += float(s['cost'])
    return count, cost


def _calculate_traffic_cost(cost_details, resource_cost):
    for resource_type in TRAFFIC_MAPPING.values():
        if resource_type in cost_details:
            (count, cost) = _calculate_count_cost(cost_details[resource_type],
                                                  resource_type)
            if cost > 0:
                resource_cost[resource_type] = (count, cost)


def _apply_discount(cost, start_str, end_str, prices):
    """Appy discount for the usage costs

    For now we only show the discount info for current month cost, because
    the discount for history month has shown on customer's invoice.
    """
    total_cost, breakdown, cost_details = cost
    start = time.mktime(time.strptime(start_str, '%Y-%m-%dT%H:%M:%S'))
    end = time.mktime(time.strptime(end_str, '%Y-%m-%dT%H:%M:%S'))
    # Get the integer part of the hours
    free_hours = math.floor((end - start) / 3600)

    free_network_cost = round(prices.get('Network', 0.0164) * free_hours, 2)
    free_router_cost = round(prices.get('Router', 0.0170) * free_hours, 2)

    for item in breakdown:
        if item.resource == 'Network':
            free_network_cost = (item.cost if item.cost <= free_network_cost
                                 else free_network_cost)
            breakdown[item.id - 1] = item._replace(cost=(item.cost -
                                                         free_network_cost))
            total_cost -= free_network_cost
        if item.resource == 'Router':
            free_router_cost = (item.cost if item.cost <= free_router_cost
                                else free_router_cost)
            breakdown[item.id - 1] = item._replace(cost=(item.cost -
                                                         free_router_cost))
            total_cost -= free_router_cost

    return (total_cost, breakdown, cost_details)


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
    if enable_eventlet:
        eventlet.monkey_patch()
    thread_pool = eventlet.GreenPool(size=12)
    history_cost = [(0, EMPTY_BREAKDOWN, []) for _ in range(12)]

    distil_client = distil_client or distilclient(request)

    if not distil_client:
        return history_cost

    today = datetime.date.today()
    start = _calculate_start_date(datetime.date.today())
    end = _calculate_end_date(start)
    final_end = datetime.datetime(today.year, today.month + 1, 1)

    try:
        for i in range(12):
            start_str = start.strftime("%Y-%m-%dT00:00:00")
            end_str = end.strftime("%Y-%m-%dT00:00:00")
            thread_pool.spawn_n(_get_month_cost,
                                distil_client, request.user.tenant_id,
                                start_str, end_str,
                                history_cost, i)
            start = end
            end = _calculate_end_date(start)
            if end > final_end:
                break

        thread_pool.waitall()
    except Exception as e:
        LOG.exception('Failed to get the history cost data', e)

    return history_cost
