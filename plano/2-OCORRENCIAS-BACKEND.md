# ✅ Ocorrências — Concluído

> Esta feature está **100% implementada**. Este documento serve como referência
> de arquitetura para as próximas features (Delays, Atestados, etc.).

---

## Arquitetura implementada

```
app/domains/occurrences/
├── __init__.py
├── models.py    ← Tabela `occurrences` no banco
├── schemas.py   ← Contratos da API (Create, Update, Public, List)
└── routers.py   ← Endpoints FastAPI com RBAC
```

---

## Endpoints

| Método | Rota                  | Permissão              | Comportamento                                          |
|--------|-----------------------|------------------------|--------------------------------------------------------|
| POST   | `/occurrences`        | OCCURRENCES_CREATE     | Cria ocorrência; `created_by_id` = usuário logado     |
| GET    | `/occurrences`        | OCCURRENCES_VIEW_ALL   | Coordenador/admin vê todas                            |
| GET    | `/occurrences/me`     | OCCURRENCES_VIEW_OWN   | Aluno vê as suas; professor vê as que criou           |
| GET    | `/occurrences/{id}`   | OCCURRENCES_VIEW_OWN   | Aluno só vê as próprias; professor/coord vê qualquer  |
| PUT    | `/occurrences/{id}`   | OCCURRENCES_EDIT       | Professor só edita as que criou; coord edita qualquer |
| DELETE | `/occurrences/{id}`   | OCCURRENCES_DELETE     | Mesma regra do PUT                                     |

---

## Decisões de design relevantes

### Por que não há `relationship()` no model `Occurrence`?
O SQLAlchemy 2.x com `mapped_as_dataclass` tem um bug: após `session.refresh()`,
um `relationship` com `lazy='noload'` e `default=None` sobrescreve a FK escalar
(`created_by_id`) com `None` em memória, mesmo que o valor esteja correto no banco.

Como `OccurrencePublic` usa apenas os campos escalares (`student_id`, `created_by_id`),
os relationships são desnecessários e foram omitidos para evitar o bug.

### Por que `_get_occurrence_or_404` e `_assert_can_modify` são funções auxiliares?
Para evitar repetição nas rotas PUT e DELETE, que têm exatamente a mesma
lógica de busca e verificação de autoria. Mantém os handlers curtos e legíveis.

### Por que `created_by_id` usa `SET NULL` e não `CASCADE`?
Se o professor que criou a ocorrência for deletado do sistema, a ocorrência
deve ser preservada (é um registro histórico). O campo `created_by_id` vira
`None`, mas os dados da ocorrência permanecem.

Ao contrário, `student_id` usa `CASCADE`: se o aluno for deletado, suas
ocorrências não fazem mais sentido e são deletadas junto.

---

## Padrão para novas features

Use esta estrutura como modelo ao implementar Delays, Atestados, etc.:

```python
# routers.py — padrão de rota com permissão e helper de 404
@router.post(
    '/',
    status_code=HTTPStatus.CREATED,
    response_model=FeaturePublic,
    dependencies=[Depends(PermissionChecker({SystemPermissions.FEATURE_CREATE}))],
)
async def create_feature(data: FeatureCreate, session: Session, current_user: CurrentUser):
    ...

async def _get_feature_or_404(feature_id: int, session: AsyncSession) -> Feature:
    feature = await session.scalar(select(Feature).where(Feature.id == feature_id))
    if not feature:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='Feature not found')
    return feature
```
