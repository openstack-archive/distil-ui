# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock

from openstack_dashboard.test.test_data import utils

from distil_ui.test import test_data

TEST = utils.TestData(test_data.data)


def mock_resource(resource):
    """Utility function to make mocking more DRY"""

    mocked_data = \
        [mock.Mock(**{'to_dict.return_value': item}) for item in resource]

    return mocked_data
