from datetime import datetime, time, timedelta

from app.domains.schedules.schemas import Period, PeriodsList


def to_datetime(t: time) -> datetime:
    """
    Converte um objeto time para datetime.
    Necessário porque operações com timedelta funcionam melhor com datetime.
    """
    return datetime.combine(datetime.today(), t)


def add_time(t: time, delta: timedelta) -> time:
    """
    Soma um horário (time) com um timedelta.

    Exemplo:
    07:30 + 50min → 08:20
    """
    return (to_datetime(t) + delta).time()


def overlaps(start1: time, end1: time, start2: time, end2: time) -> bool:
    """
    Verifica sobreposição com intervalos que podem cruzar a meia-noite.
    Logica: (StartA < EndB) AND (EndA > StartB) adaptada para ciclos de 24h.
    """
    # Se o intervalo 1 cruza a meia-noite (ex: 23:00 às 01:00)
    # ele é tratado como: (start1 até 24:00) OU (00:00 até end1)

    def get_intervals(s: time, e: time):
        if s < e:
            return [(s, e)]
        return [(s, time(23, 59, 59, 999999)), (time(0, 0), e)]

    intervals1 = get_intervals(start1, end1)
    intervals2 = get_intervals(start2, end2)

    for s1, e1 in intervals1:
        for s2, e2 in intervals2:
            if s1 < e2 and e1 > s2:
                return True
    return False


def _build_periods() -> PeriodsList:
    """
    Gera automaticamente os períodos de aula,
    incluindo intervalos (breaks) em ordem cronológica.
    """

    # Quantidade total de aulas no dia
    num_periods = 9

    # Duração de cada aula
    period_duration = timedelta(minutes=50)
    # Exemplo: timedelta(hours=1, minutes=10)

    # Horário inicial do dia
    current_start = time(7, 30)

    # Lista de intervalos (ordem crescente é importante)
    breaks = [
        Period(
            type='snack_break',
            period_number=None,
            start=time(9, 10),
            end=time(9, 30),
        ),
        Period(
            type='lunch_break',
            period_number=None,
            start=time(12, 0),
            end=time(13, 20),
        ),
        Period(
            type='snack_break',
            period_number=None,
            start=time(15, 0),
            end=time(15, 20),
        ),
    ]

    # Garante que os intervalos estão ordenados por horário de início
    breaks.sort(key=lambda b: b.start)

    # Lista final de períodos gerados (aulas + intervalos)
    periods: list[Period] = []

    # Contador de aulas (começando em 1 para ficar mais natural)
    period_number = 1

    # Controle para evitar adicionar o mesmo intervalo mais de uma vez
    added_breaks = set()

    # Loop principal: gera até atingir o número desejado de aulas
    while period_number <= num_periods:
        # Calcula o horário de término da aula atual
        current_end = add_time(current_start, period_duration)

        # Verifica se essa aula colide com algum intervalo
        collided_break = next(
            (
                b
                for b in breaks
                if overlaps(current_start, current_end, b.start, b.end)
            ),
            None,
        )

        # Se houve colisão com intervalo:
        if collided_break:
            # Adiciona o intervalo na lista final (uma única vez)
            if id(collided_break) not in added_breaks:
                periods.append(collided_break)
                added_breaks.add(id(collided_break))

            # "Pula" diretamente para o fim do intervalo
            # evitando criar aulas inválidas
            current_start = collided_break.end
            continue

        # Cria o período de aula
        periods.append(
            Period(
                type='class_period',
                period_number=period_number,
                start=current_start,
                end=current_end,
            )
        )

        # Incrementa o número da aula
        period_number += 1

        # Próxima aula começa onde a anterior terminou
        current_start = current_end

    # Retorna encapsulado no modelo
    return PeriodsList(periods=periods)


# Geração automática ao importar o módulo
PERIODS = _build_periods()
