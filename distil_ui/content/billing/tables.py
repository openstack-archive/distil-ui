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

from django.utils.translation import ugettext_lazy as _

from horizon import tables


class CSVSummary(tables.LinkAction):
    name = "csv_summary"
    verbose_name = _("Download CSV Summary")
    icon = "download"

    def get_link_url(self):
        return self.table.kwargs['billing'].csv_link()


class BillingTable(tables.DataTable):
    resource = tables.Column("resource",
                             link=("#"),
                             verbose_name=_("Resource"))
    count = tables.Column("count", verbose_name=_("Count"))
    cost = tables.Column("cost", verbose_name=_("Cost"))

    class Meta(object):
        name = "billing"
        verbose_name = _("Breakdown")
        columns = ("resource", "count", "cost")
        table_actions = (CSVSummary,)
        multi_select = False
