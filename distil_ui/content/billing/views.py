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
from django.utils.translation import ugettext_lazy as _
import json
import logging

from horizon import exceptions
from horizon import views

from distil_ui.api import distil_v2 as distil

LOG = logging.getLogger(__name__)


class IndexView(views.HorizonTemplateView):
    template_name = 'management/billing/index.html'

    def __init__(self, *args, **kwargs):
        super(IndexView, self).__init__(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        try:
            distil_client = distil.distilclient(self.request)
            self.cost = distil.get_cost(self.request, distil_client)
            self.credits = distil.get_credits(self.request, distil_client)
            pie_data = []
            for i in range(len(self.cost)):
                pie_data.append([{"value": value, "key": key} for (key, value)
                                in self.cost[i]["breakdown"].items()])
            line_data = [{"values": [{"y": round(m["total_cost"], 2), "x": i,
                                      "p": m.get("status")} for i, m
                          in enumerate(self.cost)], "key": "Cost"}]
            context['line_chart_data'] = json.dumps(line_data)
            context['pie_chart_data'] = json.dumps(pie_data)
            context['month_details'] = json.dumps([d["details"] for d
                                                   in self.cost])
            context['credits'] = json.dumps(self.credits)
        except Exception as e:
            LOG.exception(e)
            msg = _("Failed to load usage data, please try again. If it is "
                    "still not working, please open a support ticket.")
            exceptions.handle(self.request, msg)
            # data for place holder
            context['line_chart_data'] = json.dumps([{"values": [{"y": 0,
                                                                  "x": i}
                                                      for i in range(12)]}])
            context['pie_chart_data'] = json.dumps([{"value": 0,
                                                     "key": "N/A"}])
            context['month_details'] = json.dumps([])
            context['credits'] = json.dumps({"credits": []})

        context['x_axis_line_chart'] = self._get_x_axis_for_line_chart()
        return context

    def _get_x_axis_for_line_chart(self):
        today = datetime.date.today()
        ordered_month = ['Jan ', 'Feb ', 'Mar ', "Apr ", 'May ', 'Jun ',
                         'Jul ', 'Aug ', 'Sep ', 'Oct ', 'Nov ', 'Dec ']

        return ([m + str(today.year - 1) for m in ordered_month[today.month:]]
                + [m + str(today.year) for m in ordered_month[:today.month]])
