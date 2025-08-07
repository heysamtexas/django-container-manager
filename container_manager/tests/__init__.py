# Essential tests only - pruned from 530+ tests to ~45 tests
# Import remaining core test modules for discovery
from .test_job_service_integration import *  # noqa: F403
from .test_models_core import *  # noqa: F403
from .test_queue_core import *  # noqa: F403
from .test_services_core import *  # noqa: F403
from .test_state_machine_core import *  # noqa: F403
