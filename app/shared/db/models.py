# Importa TODOS os models para registrar no mapper_registry

from app.domains.users import models as user_models  # noqa: F401, I001
from app.domains.occurrences import models as occurences_models  # noqa: F401
