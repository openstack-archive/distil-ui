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

import datetime
import json
import logging

from django.template import defaultfilters
from django.utils.translation import ugettext_lazy as _
from horizon import exceptions
from horizon import tables as horizon_tables
from horizon.utils import csvbase

from distil_ui.api import distil_v2 as distil
from distil_ui.content.billing import base
from distil_ui.content.billing import tables

LOG = logging.getLogger(__name__)


class IndexCsvRenderer(csvbase.BaseCsvResponse):
    columns = [_("Resource"), _("Count"), _("Cost")]

    def get_row_data(self):
        for b in self.context['current_month']:
            yield (b.resource,
                   b.count,
                   defaultfilters.floatformat(b.cost, 2))


class IndexView(horizon_tables.DataTableView):
    table_class = tables.BillingTable
    show_terminated = True
    csv_template_name = 'management/billing/billing.csv'
    template_name = 'management/billing/index.html'
    csv_response_class = IndexCsvRenderer

    def __init__(self, *args, **kwargs):
        super(IndexView, self).__init__(*args, **kwargs)

    def get_template_names(self):
        if self.request.GET.get('format', 'html') == 'csv':
            return (self.csv_template_name or
                    ".".join((self.template_name.rsplit('.', 1)[0], 'csv')))
        return self.template_name

    def get_content_type(self):
        if self.request.GET.get('format', 'html') == 'csv':
            return "text/csv"
        return "text/html"

    def get_data(self):
        try:
            project_id = self.kwargs.get('project_id',
                                         self.request.user.tenant_id)
            self.billing = base.BaseBilling(self.request, project_id)
            self.start, self.end = self.billing.get_date_range()
            distil_client = distil.distilclient(self.request)
            self.cost = distil.get_cost(self.request, distil_client)
            self.credits = distil.get_credits(self.request, distil_client)
            self.kwargs['billing'] = self.billing
            self.kwargs['cost'] = self.cost
            return self.cost[-1]
        except Exception as e:
            LOG.exception(e)
            exceptions.handle(self.request, _('Unable to get usage cost.'))
            self.kwargs['billing'] = None
            self.kwargs['history'] = [{} for i in range(12)]
            return []

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        try:
            context['form'] = self.billing.form
            context['billing'] = self.billing
            pie_data = []
            for i in range(len(self.cost)):
                pie_data.append([{"value": value, "key": key} for (key, value)
                                 in self.cost[i]["breakdown"].items()])
            avg_cost = sum([m["total_cost"] for m in self.cost[:11]]) / 11.0
            line_data = [{"values": [{"y": m["total_cost"], "x": i,
                                      "p": m["status"]} for i, m
                                     in enumerate(self.cost)], "key": "Cost"},
                         {"values": [{"y": avg_cost, "x": i}
                                     for i in range(12)],
                          "key": "Avg Cost", "color": "#fdd0a2"}]

            context['line_chart_data'] = json.dumps(line_data)
            context['pie_chart_data'] = json.dumps(pie_data)
            context['month_details'] = json.dumps([d["details"] for d
                                                   in self.cost])
            context['x_axis_line_chart'] = self._get_x_axis_for_line_chart()
            context['credits'] = json.dumps(self.credits)
        except Exception as e:
            LOG.exception(e)
        return context

    def _get_x_axis_for_line_chart(self):
        today = datetime.date.today()
        ordered_month = ['Jan ', 'Feb ', 'Mar ', "Apr ", 'May ', 'Jun ',
                         'Jul ', 'Aug ', 'Sep ', 'Oct ', 'Nov ', 'Dec ']

        return ([m + str(today.year - 1) for m in ordered_month[today.month:]]
                + [m + str(today.year) for m in ordered_month[:today.month]])

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('format', 'html') == 'csv':
            render_class = self.csv_response_class
            fn_template = "usage_cost_{0}_{1}.csv"
            filename = fn_template.format(self.start.strftime('%Y-%m-%d'),
                                          self.end.strftime('%Y-%m-%d'))
            response_kwargs.setdefault("filename", filename)
        else:
            render_class = self.response_class
        resp = render_class(request=self.request,
                            template=self.get_template_names(),
                            context=context,
                            content_type=self.get_content_type(),
                            **response_kwargs)
        return resp
