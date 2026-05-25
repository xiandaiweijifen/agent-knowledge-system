# Import all adapter modules to trigger their register_adapter() calls.
from app.services.agent.adapters import document_search  # noqa: F401
from app.services.agent.adapters import service_dependencies  # noqa: F401
from app.services.agent.adapters import system_status  # noqa: F401
from app.services.agent.adapters import ticketing  # noqa: F401
