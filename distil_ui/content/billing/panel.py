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

import horizon

# NOTE(flwang): By default, this billing panel is expecting there is
# a management dashboard under contrib.
try:
    from openstack_dashboard.contrib.management import dashboard
except Exception:
    from openstack_dashboard.dashboards.project import dashboard


class Billing(horizon.Panel):
    name = _("Usage Costs")
    slug = 'billing'

try:
    dashboard.ManagementDashboard.register(Billing)
except Exception:
    dashboard.Project.register(Billing)
