import csv
import os

# ============================================================
# CONFIGURAÇÕES: Informe os caminhos dos arquivos
# ============================================================
MOSTRAR_PROFESSORES = False
MOSTRAR_DISCIPLINAS = False

SEG_TXT = '../data/horarios/informacoes/segunda.txt'  # Caminho para o horário de Segunda-feira
TER_TXT = '../data/horarios/informacoes/terca.txt'  # Terça-feira
QUA_TXT = '../data/horarios/informacoes/quarta.txt'  # Quarta-feira
QUI_TXT = '../data/horarios/informacoes/quinta.txt'  # Quinta-feira
SEX_TXT = '../data/horarios/informacoes/sexta.txt'  # Sexta-feira

PROFESSORES_CSV = '../data/horarios/informacoes/relacao_professores_email.csv'  # CSV com colunas: nome,email_professor
DISCIPLINAS_CSV = '../data/horarios/informacoes/relacao_sigla_disciplina_nome.csv'  # CSV com colunas: sigla,nome (nome completo)
OUTPUT_DIR = '../data/horarios'  # Onde salvar os CSVs das salas (None = mesmo dir do script)
# ============================================================
# Mapeamento dia da semana: nome -> número
# ============================================================
dias = {
    'seg': 2,  # Segunda-feira
    'ter': 3,  # Terça-feira
    'qua': 4,  # Quarta-feira
    'qui': 5,  # Quinta-feira
    'sex': 6,  # Sexta-feira
}

# ------------------------------------------------------------
# Intervalos fixos (conforme horario_sala_base.csv)
# ------------------------------------------------------------
# Estrutura: (dia_semana, tipo, titulo)
intervalos = [
    (2, 'snack_break', 'Intervalo da Manhã'),
    (2, 'snack_break', 'Intervalo da Tarde'),
    (2, 'lunch_break', 'Almoço'),
    (3, 'snack_break', 'Intervalo da Manhã'),
    (3, 'snack_break', 'Intervalo da Tarde'),
    (3, 'lunch_break', 'Almoço'),
    (4, 'snack_break', 'Intervalo da Manhã'),
    (4, 'snack_break', 'Intervalo da Tarde'),
    (4, 'lunch_break', 'Almoço'),
    (5, 'snack_break', 'Intervalo da Manhã'),
    (5, 'snack_break', 'Intervalo da Tarde'),
    (5, 'lunch_break', 'Almoço'),
    (6, 'snack_break', 'Intervalo da Manhã'),
    (6, 'snack_break', 'Intervalo da Tarde'),
    (6, 'lunch_break', 'Almoço'),
]

# ------------------------------------------------------------
# Obtém o diretório onde este script está localizado
# ------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve_path(path):
    """Converte um caminho (relativo ou absoluto) para absoluto baseado no diretório do script."""
    if os.path.isabs(path):
        return path
    return os.path.join(SCRIPT_DIR, path)


# ------------------------------------------------------------
# Carrega o CSV de professores e retorna um dicionário {nome: email}
# ------------------------------------------------------------
def load_professores(csv_path):
    abs_path = resolve_path(csv_path)
    if not os.path.exists(abs_path):
        print(
            f'Aviso: Arquivo de professores não encontrado em {abs_path}. Usando nomes como emails.'
        )
        return {}

    mapping = {}
    with open(abs_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if (
            'nome' not in reader.fieldnames
            or 'email_professor' not in reader.fieldnames
        ):
            print(
                "Erro: O CSV de professores deve ter as colunas 'nome' e 'email_professor'."
            )
            return {}
        for row in reader:
            nome = row['nome'].strip()
            email = row['email_professor'].strip()
            if nome and email:
                mapping[nome] = email
    print(f'Carregados {len(mapping)} professores do arquivo {abs_path}')
    return mapping


# ------------------------------------------------------------
# Carrega o CSV de disciplinas e retorna um dicionário {sigla: nome_completo}
# ------------------------------------------------------------
def load_disciplinas(csv_path):
    abs_path = resolve_path(csv_path)
    if not os.path.exists(abs_path):
        print(
            f'Aviso: Arquivo de disciplinas não encontrado em {abs_path}. Usando siglas originais.'
        )
        return {}

    mapping = {}
    with open(abs_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if 'sigla' not in reader.fieldnames or 'nome' not in reader.fieldnames:
            print(
                "Erro: O CSV de disciplinas deve ter as colunas 'sigla' e 'nome'."
            )
            return {}
        for row in reader:
            sigla = row['sigla'].strip()
            nome = row['nome'].strip()
            if sigla and nome:
                mapping[sigla] = nome
    print(f'Carregadas {len(mapping)} disciplinas do arquivo {abs_path}')
    return mapping


# ------------------------------------------------------------
# Função para ler e parsear o conteúdo de um dia
# Retorna dicionário: periodo -> (lista_disciplinas, lista_professores)
# ------------------------------------------------------------
def parse_day(text):
    lines = text.splitlines()
    i = 0
    data = {}
    while i < len(lines):
        line = lines[i].strip()
        if line and line[-1] == 'º' and line[:-1].isdigit():
            period = int(line[:-1])
            i += 1
            subjects = []
            for _ in range(12):
                if i >= len(lines):
                    break
                subjects.append(lines[i].strip())
                i += 1
            if i < len(lines) and lines[i].strip() == 'AULA':
                i += 1
            else:
                break
            teachers = []
            for _ in range(12):
                if i >= len(lines):
                    break
                teachers.append(lines[i].strip())
                i += 1
            data[period] = (subjects, teachers)
        else:
            i += 1
    return data


# ------------------------------------------------------------
# Carrega conteúdo do arquivo (com resolução de caminho)
# ------------------------------------------------------------
def load_txt_file(rel_path):
    abs_path = resolve_path(rel_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f'Arquivo não encontrado: {abs_path}')
    with open(abs_path, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

# 1. Carregar mapeamentos
prof_mapping = load_professores(PROFESSORES_CSV)
disc_mapping = load_disciplinas(DISCIPLINAS_CSV)

# 2. Conjuntos para armazenar nomes de professores e siglas de disciplinas (originais dos TXTs)
professores_encontrados = set()
disciplinas_encontradas = set()

# 3. Estrutura para armazenar todas as aulas: sala -> lista de linhas CSV
salas = {sala_id: [] for sala_id in range(1, 13)}  # 1 a 12

# 4. Processar cada dia da semana (aulas)
for dia_nome, dia_num in dias.items():
    if dia_nome == 'seg':
        txt_path = SEG_TXT
    elif dia_nome == 'ter':
        txt_path = TER_TXT
    elif dia_nome == 'qua':
        txt_path = QUA_TXT
    elif dia_nome == 'qui':
        txt_path = QUI_TXT
    elif dia_nome == 'sex':
        txt_path = SEX_TXT
    else:
        continue

    try:
        conteudo = load_txt_file(txt_path)
    except FileNotFoundError as e:
        print(f'Erro: {e}. Pulando {dia_nome}.')
        continue

    periodos = parse_day(conteudo)
    if not periodos:
        print(
            f'Aviso: Nenhum período encontrado em {txt_path}. Verifique o formato.'
        )
        continue

    for periodo, (subjects, teachers) in periodos.items():
        for idx in range(12):
            sala_id = idx + 1
            sigla_disciplina = subjects[idx] if idx < len(subjects) else ''
            nome_prof = teachers[idx] if idx < len(teachers) else ''

            # Adiciona aos conjuntos (dados brutos do TXT)
            if sigla_disciplina:
                disciplinas_encontradas.add(sigla_disciplina)
            if nome_prof:
                professores_encontrados.add(nome_prof)

            # Aplica mapeamento de disciplina (se existir)
            nome_disciplina = disc_mapping.get(
                sigla_disciplina, sigla_disciplina
            )
            # Busca o email do professor
            email_prof = prof_mapping.get(nome_prof, nome_prof)

            salas[sala_id].append({
                'email_professor': email_prof,
                'dia_semana': dia_num,
                'numero_periodo': periodo,
                'tipo': 'class_period',
                'titulo': nome_disciplina,
            })

# 5. Adicionar os intervalos para todas as salas
for sala_id in range(1, 13):
    for dia, tipo, titulo in intervalos:
        salas[sala_id].append({
            'email_professor': '',  # vazio conforme CSV original
            'dia_semana': dia,
            'numero_periodo': '',  # vazio
            'tipo': tipo,
            'titulo': titulo,
        })

# 6. (Opcional) Exibir os conjuntos coletados – linhas comentadas
# print("\n--- PROFESSORES ENCONTRADOS (nomes originais) ---")
# for nome in sorted(professores_encontrados):
#     print(nome)
# print(f"\nTotal: {len(professores_encontrados)} professores")
#
# print("\n--- DISCIPLINAS ENCONTRADAS (siglas originais) ---")
# for sigla in sorted(disciplinas_encontradas):
#     print(sigla)
# print(f"\nTotal: {len(disciplinas_encontradas)} disciplinas")

# 7. Definir diretório de saída dos CSVs
if OUTPUT_DIR is None:
    output_dir = SCRIPT_DIR
else:
    output_dir = resolve_path(OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)

print(f'Salvando arquivos CSV em: {output_dir}')

# 8. Gerar um arquivo CSV para cada sala
for sala_id in range(1, 13):
    filename = f'horario_sala_{sala_id}.csv'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'email_professor',
                'dia_semana',
                'numero_periodo',
                'tipo',
                'titulo',
            ],
        )
        writer.writeheader()
        # Ordena: primeiro por dia da semana, depois por período (os intervalos têm periodo vazio, ficarão no início ou fim?
        # Para manter a ordem original do CSV base, deixamos como estão. Se quiser ordenar, use key com tratamento especial.
        # Como o CSV original não ordena, apenas mantemos a ordem de inserção (primeiro as aulas, depois os intervalos).
        # Mas para reproduzir exatamente o base, você pode querer misturar? O base tem intervalos antes das aulas.
        # Vou manter a ordem: primeiro as aulas (já ordenadas por dia/periodo), depois os intervalos (sem ordenação).
        # Se quiser intercalar, será mais complexo. O usuário disse que o código que importa já trata isso, então OK.
        writer.writerows(salas[sala_id])

print(
    'Arquivos gerados com sucesso: horario_sala_1.csv a horario_sala_12.csv (incluindo intervalos)'
)
