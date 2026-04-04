# Importa TODOS os models para registrar no mapper_registry

from app.domains.users import models as user_models  # noqa: F401
from app.domains.occurrences import models as occurrences_models  # noqa: F401
from app.domains.schedules import models as schedules_models  # noqa: F401
from app.domains.delays import models as delays_models  # noqa: F401
