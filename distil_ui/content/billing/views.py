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

from horizon import views

from distil_ui.api import distil_v2 as distil

LOG = logging.getLogger(__name__)


class IndexView(views.HorizonTemplateView):
    template_name = 'management/billing/index.html'

    def __init__(self, *args, **kwargs):
        super(IndexView, self).__init__(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        distil_client = distil.distilclient(self.request)
        self.cost = distil.get_cost(self.request, distil_client)
        self.credits = distil.get_credits(self.request, distil_client)
        pie_data = []
        for i in range(len(self.cost)):
            pie_data.append([{"value": value, "key": key} for (key, value)
                             in self.cost[i]["breakdown"].items()])
        avg_cost = round(sum([m["total_cost"]
                              for m in self.cost[:11]]) / 11.0, 2)
        line_data = [{"values": [{"y": m["total_cost"], "x": i,
                                  "p": m.get("status")} for i, m
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
        return context

    def _get_x_axis_for_line_chart(self):
        today = datetime.date.today()
        ordered_month = ['Jan ', 'Feb ', 'Mar ', "Apr ", 'May ', 'Jun ',
                         'Jul ', 'Aug ', 'Sep ', 'Oct ', 'Nov ', 'Dec ']

        return ([m + str(today.year - 1) for m in ordered_month[today.month:]]
                + [m + str(today.year) for m in ordered_month[:today.month]])
