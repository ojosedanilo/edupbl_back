# 🧭 Dashboard — Controle de Features por Permissão

> Como exibir (ou ocultar) cards e rotas na dashboard com base nas
> permissões reais do usuário, obtidas da API.

---

## 🎯 Objetivo

A `HomePage` atual mostra todos os cards para todos os usuários. O objetivo é:

- Mostrar apenas os cards que o usuário tem permissão de acessar
- Bloquear o acesso direto às rotas via URL também
- Aproveitar a infra já existente (`/auth/me` e `/auth/me/permissions`)

---

## 🔍 O que a API já oferece

Você tem dois endpoints úteis:

- `GET /auth/me` → retorna `UserMe` (role, is_tutor, etc.) — **já em cache** como `["me"]`
- `GET /auth/me/permissions` → retorna lista de strings de permissão do usuário logado

Para o controle de dashboard, o mais correto é usar `GET /auth/me/permissions`, porque:

- Centraliza a lógica de "quem pode o quê" no backend (onde já está definida)
- `is_tutor` muda o conjunto de permissões do professor, e isso já está tratado no backend
- Se o RBAC evoluir (novas roles, permissões por turma), o frontend não precisa mudar

---

## 📐 Modelo de dados do frontend

### Atualizar `UserMe`

Adicionar o campo `permissions` ao tipo, buscando de `/auth/me/permissions`:

```ts
// src/features/auth/models/UserMe.ts

export interface UserMe {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  is_tutor: boolean;
  is_active: boolean;
  classroom_id: number | null;
  must_change_password: boolean;
}

// Permissões separadas — buscadas de /auth/me/permissions
export interface UserPermissions {
  permissions: string[];
}
```

### Adicionar constantes de permissão no frontend

Cria um arquivo espelhando o `SystemPermissions` do backend:

```ts
// src/features/auth/models/Permissions.ts

export const Permissions = {
  // Atrasos
  DELAYS_CREATE:          'delays:create',
  DELAYS_APPROVE:         'delays:approve',
  DELAYS_REJECT:          'delays:reject',
  DELAYS_VIEW_ALL:        'delays:read_all',
  DELAYS_VIEW_OWN:        'delays:read_own',
  DELAYS_VIEW_CHILD:      'delays:read_child',
  DELAYS_VIEW_OWN_CLASS:  'delays:read_own_class',

  // Ocorrências
  OCCURRENCES_CREATE:     'occurrences:create',
  OCCURRENCES_VIEW_ALL:   'occurrences:read_all',
  OCCURRENCES_VIEW_OWN:   'occurrences:read_own',
  OCCURRENCES_VIEW_CHILD: 'occurrences:read_child',

  // Horários
  SCHEDULES_VIEW:         'schedules:view',
  SCHEDULES_MANAGE:       'schedules:manage',

  // Usuários
  USER_VIEW_ALL:          'users:read_all',
  USER_CREATE:            'user:create',
  USER_EDIT:              'user:update',
  USER_DELETE:            'user:delete',
  USER_CHANGE_ROLE:       'user:change_role',

  // Relatórios
  REPORTS_VIEW_ALL:       'reports:view_all',
  REPORTS_VIEW_OWN_CLASS: 'reports:view_own_class',

  // Espaços
  SPACES_VIEW_ALL:        'spaces:read_all',
  SPACES_RESERVATE:       'spaces:reservate',
  SPACES_MANAGE:          'spaces:manage', // create + edit + delete

  // Sugestões
  SUGGESTIONS_SUBMIT:     'suggestions:submit',
  SUGGESTIONS_MODERATE:   'suggestions:moderate',
} as const;

export type Permission = typeof Permissions[keyof typeof Permissions];
```

---

## 🔌 Hook: `usePermissions`

Busca as permissões do usuário e expõe um helper `can(permission)`:

```ts
// src/features/auth/hooks/usePermissions.ts

import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';
import { useCurrentUser } from './useAuth';
import type { Permission } from '../models/Permissions';

export const PERMISSIONS_QUERY_KEY = ['me', 'permissions'] as const;

async function fetchPermissions(): Promise<string[]> {
  const { data } = await api.get<{ permissions: string[] }>('/auth/me/permissions');
  return data.permissions;
}

/**
 * Retorna as permissões do usuário logado e um helper `can()`.
 *
 * - Só faz a query se o usuário estiver autenticado
 * - staleTime: Infinity — as permissões só mudam com login/logout
 * - Invalide com queryClient.invalidateQueries(['me', 'permissions'])
 *   se um admin alterar a role do usuário durante a sessão
 */
export function usePermissions() {
  const { user } = useCurrentUser();

  const { data: permissions = [], isLoading } = useQuery({
    queryKey: PERMISSIONS_QUERY_KEY,
    queryFn: fetchPermissions,
    enabled: !!user,           // só busca se logado
    staleTime: Infinity,       // permissões mudam só com login/logout
  });

  /** Verifica se o usuário possui uma permissão específica. */
  function can(permission: Permission): boolean {
    return permissions.includes(permission);
  }

  /**
   * Verifica se o usuário possui ao menos uma das permissões listadas.
   * Útil para cards que correspondem a múltiplas permissões (ex: ocorrências).
   */
  function canAny(...perms: Permission[]): boolean {
    return perms.some((p) => permissions.includes(p));
  }

  return { permissions, can, canAny, isLoading };
}
```

### Invalidar ao fazer logout

No `useLogout`, adicione a invalidação das permissões junto com `["me"]`:

```ts
// useAuth.ts — onSettled do useLogout
onSettled: () => {
  clearAccessToken();
  queryClient.setQueryData<null>(ME_QUERY_KEY, null);
  queryClient.removeQueries({ queryKey: ME_QUERY_KEY });         // remove ["me"]
  queryClient.removeQueries({ queryKey: ['me', 'permissions'] }); // remove ["me", "permissions"]
  navigate('/entrar', { replace: true });
},
```

---

## 🏠 Atualizar `HomePage`

### Estrutura de um card de feature

```ts
// src/features/dashboard/featureCards.tsx

import type { Permission } from '@/features/auth/models/Permissions';
import { Permissions } from '@/features/auth/models/Permissions';
import type { ReactNode } from 'react';

// Importações de ícones MUI (já usados na HomePage atual)
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import AccessTimeIcon     from '@mui/icons-material/AccessTime';
import PeopleIcon         from '@mui/icons-material/People';
import SchoolIcon         from '@mui/icons-material/School';
import MeetingRoomIcon    from '@mui/icons-material/MeetingRoom';
import FactCheckIcon      from '@mui/icons-material/FactCheck';
import CalendarMonthIcon  from '@mui/icons-material/CalendarMonth';
import MenuBookIcon       from '@mui/icons-material/MenuBook';
import EventIcon          from '@mui/icons-material/Event';

export interface FeatureCardConfig {
  icon: ReactNode;
  title: string;
  description: string;
  to: string;
  /**
   * O card aparece se o usuário tiver AO MENOS UMA das permissões listadas.
   * Se vazio, o card aparece para todos os usuários autenticados.
   */
  requiredPermissions: Permission[];
}

export const FEATURE_CARDS: FeatureCardConfig[] = [
  {
    icon: <ReportProblemIcon className="text-accent" />,
    title: 'Ocorrências',
    description: 'Visualize, registre e gerencie ocorrências disciplinares.',
    to: '/ocorrencias',
    requiredPermissions: [
      Permissions.OCCURRENCES_CREATE,
      Permissions.OCCURRENCES_VIEW_ALL,
      Permissions.OCCURRENCES_VIEW_OWN,
      Permissions.OCCURRENCES_VIEW_CHILD,
    ],
  },
  {
    icon: <AccessTimeIcon className="text-accent" />,
    title: 'Atrasos',
    description: 'Controle e registre atrasos dos alunos.',
    to: '/atrasos',
    requiredPermissions: [
      Permissions.DELAYS_CREATE,
      Permissions.DELAYS_APPROVE,
      Permissions.DELAYS_VIEW_ALL,
      Permissions.DELAYS_VIEW_OWN,
      Permissions.DELAYS_VIEW_CHILD,
      Permissions.DELAYS_VIEW_OWN_CLASS,
    ],
  },
  {
    icon: <CalendarMonthIcon className="text-accent" />,
    title: 'Horários',
    description: 'Consulte e gerencie os horários das turmas.',
    to: '/horarios',
    requiredPermissions: [
      Permissions.SCHEDULES_VIEW,
      Permissions.SCHEDULES_MANAGE,
    ],
  },
  {
    icon: <PeopleIcon className="text-accent" />,
    title: 'Usuários',
    description: 'Gerencie alunos, professores e responsáveis.',
    to: '/usuarios',
    requiredPermissions: [
      Permissions.USER_VIEW_ALL,
      Permissions.USER_CREATE,
    ],
  },
  {
    icon: <SchoolIcon className="text-accent" />,
    title: 'Turmas',
    description: 'Organize e acompanhe as turmas da escola.',
    to: '/turmas',
    requiredPermissions: [
      Permissions.USER_VIEW_ALL, // quem pode ver usuários pode ver turmas
    ],
  },
  {
    icon: <MeetingRoomIcon className="text-accent" />,
    title: 'Espaços & Mídias',
    description: 'Gerencie ambientes (biblioteca, auditório) e equipamentos.',
    to: '/recursos',
    requiredPermissions: [
      Permissions.SPACES_VIEW_ALL,
      Permissions.SPACES_RESERVATE,
    ],
  },
  {
    icon: <FactCheckIcon className="text-accent" />,
    title: 'Frequência',
    description: 'Realize chamadas e acompanhe a presença dos alunos.',
    to: '/frequencia',
    requiredPermissions: [
      Permissions.OCCURRENCES_CREATE, // professores que fazem ocorrências também fazem chamada
      Permissions.REPORTS_VIEW_ALL,
      Permissions.REPORTS_VIEW_OWN_CLASS,
    ],
  },
  {
    icon: <MenuBookIcon className="text-accent" />,
    title: 'Central Pedagógica',
    description: 'Planos de aula, banco de questões, atividades e resoluções.',
    to: '/pedagogico',
    requiredPermissions: [], // visível para todos — funcionalidade futura
  },
  {
    icon: <EventIcon className="text-accent" />,
    title: 'Eventos',
    description: 'Crie e acompanhe eventos e atividades escolares.',
    to: '/eventos',
    requiredPermissions: [], // visível para todos — funcionalidade futura
  },
];
```

### `HomePage` atualizada

```tsx
// src/pages/HomePage.tsx

import { useCurrentUser, useLogout } from '@/features/auth/hooks/useAuth';
import { usePermissions } from '@/features/auth/hooks/usePermissions';
import { FEATURE_CARDS } from '@/features/dashboard/featureCards';
import { FeatureCard } from '@/components/ui/FeatureCard';
import { GradientBackdrop } from '@/components/layout/GradientBackdrop';
import { Button } from '@/components/ui/Button';
import LogoPBL from '@/assets/logo_pbl.svg';

function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    student:     'Aluno(a)',
    guardian:    'Responsável',
    teacher:     'Professor(a)',
    coordinator: 'Coordenador(a)',
    porter:      'Porteiro(a)',
    admin:       'Administrador(a)',
  };
  return labels[role] ?? role;
}

export default function HomePage() {
  const { user } = useCurrentUser();
  const { canAny, isLoading: isLoadingPermissions } = usePermissions();
  const { mutate: logout, isPending: isLoggingOut } = useLogout();

  // Cards que o usuário tem permissão de ver
  const visibleCards = FEATURE_CARDS.filter((card) =>
    card.requiredPermissions.length === 0 || canAny(...card.requiredPermissions)
  );

  return (
    <div className="relative min-h-screen w-full">
      <GradientBackdrop />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-6 py-10">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <img src={LogoPBL} alt="" className="size-14 object-contain" />
            <div>
              <p className="text-sm font-medium text-light/90">
                {roleLabel(user?.role ?? '')}
              </p>
              <h1 className="text-2xl font-bold text-light md:text-3xl">
                Seja bem-vindo(a), {user?.first_name}!
              </h1>
            </div>
          </div>

          <Button
            type="button"
            variant="secondary"
            onClick={() => logout()}
            disabled={isLoggingOut}
          >
            {isLoggingOut ? 'Saindo…' : 'Sair'}
          </Button>
        </header>

        <section>
          <h2 className="mb-4 text-lg font-semibold text-light/90">
            O que você quer fazer?
          </h2>

          {isLoadingPermissions ? (
            <p className="text-light/60">Carregando…</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {visibleCards.map((card) => (
                <FeatureCard
                  key={card.to}
                  icon={card.icon}
                  title={card.title}
                  description={card.description}
                  to={card.to}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
```

---

## 🔒 Proteger as rotas também

Mostrar apenas os cards certos resolve a UX, mas quem conhece a URL ainda
consegue acessar. Crie um componente de rota que verifica permissão:

```tsx
// src/routes/PermissionRoute.tsx

import { Navigate, Outlet } from 'react-router-dom';
import { usePermissions } from '@/features/auth/hooks/usePermissions';
import type { Permission } from '@/features/auth/models/Permissions';

interface Props {
  /** O usuário precisa ter ao menos UMA dessas permissões. */
  anyOf: Permission[];
}

export default function PermissionRoute({ anyOf }: Props) {
  const { canAny, isLoading } = usePermissions();

  // Enquanto as permissões carregam, não redireciona ainda
  if (isLoading) return null;

  return canAny(...anyOf) ? <Outlet /> : <Navigate to="/inicio" replace />;
}
```

### Usando nas rotas

```tsx
// src/routes/index.tsx

import { Permissions } from '@/features/auth/models/Permissions';
import PermissionRoute from '@/routes/PermissionRoute';

<Route element={<ProtectedRoutes />}>
  <Route path="/inicio" element={<HomePage />} />

  {/* Qualquer usuário logado pode ver suas próprias ocorrências */}
  <Route
    element={<PermissionRoute anyOf={[
      Permissions.OCCURRENCES_CREATE,
      Permissions.OCCURRENCES_VIEW_ALL,
      Permissions.OCCURRENCES_VIEW_OWN,
      Permissions.OCCURRENCES_VIEW_CHILD,
    ]} />}
  >
    <Route path="/ocorrencias" element={<OccurrencesPage />} />
  </Route>

  {/* Porteiro, coordenação, professor DT e aluno */}
  <Route
    element={<PermissionRoute anyOf={[
      Permissions.DELAYS_CREATE,
      Permissions.DELAYS_APPROVE,
      Permissions.DELAYS_VIEW_ALL,
      Permissions.DELAYS_VIEW_OWN,
      Permissions.DELAYS_VIEW_CHILD,
      Permissions.DELAYS_VIEW_OWN_CLASS,
    ]} />}
  >
    <Route path="/atrasos" element={<DelaysPage />} />
  </Route>

  {/* Horários — todos os logados */}
  <Route
    element={<PermissionRoute anyOf={[
      Permissions.SCHEDULES_VIEW,
      Permissions.SCHEDULES_MANAGE,
    ]} />}
  >
    <Route path="/horarios" element={<SchedulesPage />} />
  </Route>

  {/* Usuários — só coordenação e admin */}
  <Route
    element={<PermissionRoute anyOf={[Permissions.USER_VIEW_ALL]} />}
  >
    <Route path="/usuarios" element={<UsersPage />} />
  </Route>
</Route>
```

---

## 📦 Resumo dos arquivos a criar/alterar

| Arquivo | Ação |
|---|---|
| `src/features/auth/models/Permissions.ts` | Criar — constantes de permissão |
| `src/features/auth/hooks/usePermissions.ts` | Criar — hook de permissões |
| `src/features/auth/hooks/useAuth.ts` | Alterar — invalidar `["me", "permissions"]` no logout |
| `src/features/dashboard/featureCards.tsx` | Criar — configuração declarativa dos cards |
| `src/pages/HomePage.tsx` | Alterar — filtrar cards com `canAny` |
| `src/routes/PermissionRoute.tsx` | Criar — guard de rota por permissão |
| `src/routes/index.tsx` | Alterar — envolver rotas com `PermissionRoute` |

---

## 💡 Decisões de design

**Por que buscar permissões da API em vez de derivar da `role` no frontend?**
Porque `is_tutor` adiciona permissões extras ao professor sem mudar sua role. Se você
derivar as permissões da role no frontend, teria que reimplementar essa lógica duplicada.
Buscando de `/auth/me/permissions`, o backend é a única fonte de verdade.

**Por que `staleTime: Infinity` nas permissões?**
As permissões de um usuário só mudam se um admin alterar sua role — o que é raro e
acontece fora da sessão atual. Na prática, permissões valem para toda a sessão.
Se precisar forçar recarga (ex: após um admin editar um usuário), basta chamar
`queryClient.invalidateQueries(['me', 'permissions'])`.

**Por que `canAny` em vez de `can` para os cards?**
Um card de "Ocorrências" faz sentido tanto para quem cria quanto para quem visualiza.
Usar `canAny` com todas as permissões relacionadas ao domínio garante que qualquer
usuário que tenha alguma interação com aquele módulo veja o card.
