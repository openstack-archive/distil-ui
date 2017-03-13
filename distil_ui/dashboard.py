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

from distil_ui.content.billing import panel as billing_panel
from distil_ui.content.default import panel as default_panel


class ManagementDashboard(horizon.Dashboard):
    name = _("Management")
    slug = "management"
    default_panel = 'default'

try:
    slugs = dict((d.slug, d) for d in horizon.get_dashboards())
except Exception:
    slugs = {}

if 'management' not in slugs:
    horizon.register(ManagementDashboard)
    ManagementDashboard.register(default_panel.Default)
    ManagementDashboard.register(billing_panel.Billing)
else:
    slugs.get('management').register(default_panel.Default)
    slugs.get('management').register(billing_panel.Billing)
