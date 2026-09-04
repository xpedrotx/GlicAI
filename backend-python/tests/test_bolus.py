import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import bolus
from app.services.bolus import (
    _iob_de_uma_dose,
    calcular_correcao,
    calcular_dose,
    calcular_insulina_ativa,
    registrar_dose_aplicada,
)
from tests.fake_supabase import FakeSupabase

PERFIL_PADRAO = dict(meta_glicemia=100, limite_baixo=70, fator_sensibilidade=50)


def test_carboidrato_e_correcao_basico():
    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=15,
        carboidratos_g=45,
        glicemia_atual=150,
        modificadores=[],
    )

    assert resultado["hipo"] is False
    assert resultado["dose_carboidrato"] == 3.0
    assert resultado["dose_correcao"] == 1.0
    assert resultado["dose_final"] == 4.0


def test_hipoglicemia_bloqueia_calculo_de_bolus():
    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=15,
        carboidratos_g=45,
        glicemia_atual=60,
        modificadores=[],
    )

    assert resultado["hipo"] is True
    assert resultado["dose_final"] is None
    assert "meça de novo em 15 minutos" in resultado["explicacao"]


def test_correcao_zero_quando_glicemia_abaixo_da_meta():
    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=10,
        carboidratos_g=40,
        glicemia_atual=90,
        modificadores=[],
    )

    assert resultado["dose_correcao"] == 0.0
    assert resultado["dose_final"] == 4.0


def test_modificador_percentual_reduz_dose():
    modificadores = [{"id": "m1", "nome": "Exercício", "tipo_ajuste": "percentual", "valor_ajuste": -20}]

    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=10,
        carboidratos_g=40,
        glicemia_atual=100,
        modificadores=modificadores,
    )

    # subtotal=4.0 -> *0.8 = 3.2 -> sempre arredonda pra baixo -> 3.0
    assert resultado["dose_final"] == 3.0
    assert resultado["modificadores_aplicados"] == ["m1"]


def test_modificador_fixo_soma_apos_percentual():
    modificadores = [
        {"id": "m1", "nome": "Exercício", "tipo_ajuste": "percentual", "valor_ajuste": -20},
        {"id": "m2", "nome": "Doença", "tipo_ajuste": "fixo", "valor_ajuste": -1},
    ]

    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=10,
        carboidratos_g=40,
        glicemia_atual=100,
        modificadores=modificadores,
    )

    # subtotal=4.0 -> *0.8 = 3.2 -> -1 = 2.2 -> sempre arredonda pra baixo -> 2.0
    assert resultado["dose_final"] == 2.0
    assert set(resultado["modificadores_aplicados"]) == {"m1", "m2"}


def test_dose_final_sempre_arredonda_para_baixo_nunca_para_cima():
    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=10,
        carboidratos_g=39,
        glicemia_atual=100,
        modificadores=[],
    )

    # 39/10 = 3.9U de carboidrato, sem correção (glicemia == meta) -> nunca 4.0
    assert resultado["dose_final"] == 3.0


def test_correcao_sem_carboidrato_omite_linha_de_carboidrato():
    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=1,
        carboidratos_g=0,
        glicemia_atual=250,
        modificadores=[],
    )

    assert resultado["dose_carboidrato"] == 0.0
    assert resultado["dose_correcao"] == 3.0
    assert resultado["dose_final"] == 3.0
    assert "Carboidrato" not in resultado["explicacao"]
    assert "Subtotal" not in resultado["explicacao"]
    assert "Correção" in resultado["explicacao"]


def test_dose_final_nunca_fica_negativa():
    modificadores = [{"id": "m1", "nome": "Ajuste extremo", "tipo_ajuste": "fixo", "valor_ajuste": -100}]

    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=10,
        carboidratos_g=10,
        glicemia_atual=100,
        modificadores=modificadores,
    )

    assert resultado["dose_final"] == 0.0


def test_insulina_ativa_abate_do_total():
    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=1,
        carboidratos_g=0,
        glicemia_atual=250,  # correção bruta = (250-100)/50 = 3.0U
        modificadores=[],
        insulina_ativa=1.0,
    )

    # dose_correcao continua sendo a bruta (informativa); quem sofre o
    # desconto de IOB é o subtotal (carboidrato + correção).
    assert resultado["dose_correcao"] == 3.0
    assert resultado["subtotal"] == 2.0
    assert resultado["dose_final"] == 2.0
    assert "Insulina ativa" in resultado["explicacao"]


def test_insulina_ativa_abate_tambem_a_cobertura_de_carboidrato():
    """
    Reproduz o caso real relatado: 15g de carboidrato (2.1U) + correção 0
    (glicemia abaixo da meta) com 2.5U de insulina ativa. A insulina ativa
    precisa abater do total, incluindo a parte de carboidrato — não só da
    correção — senão o paciente aplicaria insulina "nova" em cima da que já
    está ativa mesmo quando ela já é maior que a dose toda.
    """
    resultado = calcular_dose(
        meta_glicemia=120,
        limite_baixo=70,
        fator_sensibilidade=30,
        gramas_por_unidade=7,
        carboidratos_g=15,
        glicemia_atual=102,
        modificadores=[],
        insulina_ativa=2.5,
    )

    assert resultado["dose_correcao"] == 0.0  # 102 < 120, sem correção
    assert resultado["subtotal"] == 0.0       # 2.1 (carb) - 2.5 (IOB) -> 0
    assert resultado["dose_final"] == 0.0


def test_insulina_ativa_nao_deixa_subtotal_negativo():
    resultado = calcular_dose(
        **PERFIL_PADRAO,
        gramas_por_unidade=1,
        carboidratos_g=0,
        glicemia_atual=150,  # correção bruta = (150-100)/50 = 1.0U
        modificadores=[],
        insulina_ativa=5.0,
    )

    assert resultado["dose_correcao"] == 1.0
    assert resultado["subtotal"] == 0.0
    assert resultado["dose_final"] == 0.0


def test_iob_de_uma_dose_decaimento_linear():
    # 4U aplicadas, meia-vida (2h de 4h) -> metade ainda ativa
    assert _iob_de_uma_dose(4.0, horas_passadas=2.0, duracao_horas=4.0) == 2.0
    # dose recém aplicada -> ainda 100% ativa
    assert _iob_de_uma_dose(4.0, horas_passadas=0.0, duracao_horas=4.0) == 4.0
    # passou da duração toda -> nada mais ativo
    assert _iob_de_uma_dose(4.0, horas_passadas=5.0, duracao_horas=4.0) == 0.0
    # duração não configurada -> sem IOB
    assert _iob_de_uma_dose(4.0, horas_passadas=1.0, duracao_horas=0) == 0.0


def _executar(coro):
    return asyncio.run(coro)


def test_calcular_insulina_ativa_soma_doses_recentes_confirmadas():
    fake = FakeSupabase()
    bolus.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.store["registros_bolus"] = [
        # aplicada há 2h, duração 4h -> ainda 50% ativa = 2.0U
        {
            "id": "1", "usuario_id": usuario_id, "dose_aplicada": 4.0,
            "horario": (agora - timedelta(hours=2)).isoformat(),
        },
        # não confirmada -> não conta
        {
            "id": "2", "usuario_id": usuario_id, "dose_aplicada": None,
            "horario": (agora - timedelta(hours=1)).isoformat(),
        },
        # aplicada há 10h, fora da janela de 4h -> não conta
        {
            "id": "3", "usuario_id": usuario_id, "dose_aplicada": 10.0,
            "horario": (agora - timedelta(hours=10)).isoformat(),
        },
    ]

    total = _executar(calcular_insulina_ativa(usuario_id, 4.0))
    assert total == pytest.approx(2.0, abs=0.01)


def test_calcular_insulina_ativa_sem_duracao_configurada_retorna_zero():
    fake = FakeSupabase()
    bolus.supabase = fake

    assert _executar(calcular_insulina_ativa(str(uuid.uuid4()), None)) == 0.0
    assert _executar(calcular_insulina_ativa(str(uuid.uuid4()), 0)) == 0.0


def test_calcular_correcao_com_iob_total_nao_fica_em_silencio():
    """
    Reproduz o caso real: duas doses recentes já cobrem a correção via IOB.
    Antes, calcular_correcao voltava None e o paciente não via explicação
    nenhuma — agora precisa vir a explicação, só sem persistir/registrar.
    """
    fake = FakeSupabase()
    bolus.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.store["perfil_glicemico"] = [
        {
            "id": "p1", "usuario_id": usuario_id, "meta_glicemia": 120,
            "limite_baixo": 70, "limite_alto": 185, "fator_sensibilidade": 30,
            "tempo_insulina_ativa_horas": 3.0,
        }
    ]
    fake.store["registros_bolus"] = [
        {
            "id": "r1", "usuario_id": usuario_id, "dose_aplicada": 6.0,
            "horario": (agora - timedelta(minutes=5)).isoformat(),
        },
    ]

    correcao = _executar(calcular_correcao(usuario_id, 300))

    assert correcao is not None
    assert correcao["dose_final"] == 0.0
    assert correcao.get("registro_id") is None
    assert "Insulina ativa" in correcao["explicacao"]
    # não deve ter persistido nada em registros_bolus (só o dado de setup existente)
    assert len(fake.store["registros_bolus"]) == 1


# --------------------------------------------------------------------------
# registrar_dose_aplicada — bug real relatado: "apliquei 10u" avulso (sem
# bolus/correção calculado antes) fazia a insulina ativa aparecer zerada
# pouco depois, porque o método antigo pegava QUALQUER último registro do
# usuário (não importa a idade) e usava o horário de CÁLCULO pra decair a
# IOB, em vez de gravar/usar o horário real da aplicação.
# --------------------------------------------------------------------------

def test_apliquei_avulso_sem_calculo_previo_cria_registro_e_conta_como_iob():
    fake = FakeSupabase()
    bolus.supabase = fake
    usuario_id = str(uuid.uuid4())

    # Nenhum registros_bolus prévio — paciente nunca mandou "bolus"/"glicemia"
    # com correção sugerida, só sabe a própria dose e manda "apliquei 10".
    registro = _executar(registrar_dose_aplicada(usuario_id, 10.0))

    assert registro is not None
    assert registro["dose_aplicada"] == 10.0
    assert registro["glicemia_referencia"] is None
    assert registro["horario_aplicacao"] is not None

    # ~1h09 depois (o cenário real relatado), com tempo de insulina ativa de
    # 4h, ainda deve sobrar insulina ativa — não pode estar zerada.
    fake.store["registros_bolus"][0]["horario_aplicacao"] = (
        datetime.now(timezone.utc) - timedelta(hours=1, minutes=9)
    ).isoformat()

    total = _executar(calcular_insulina_ativa(usuario_id, 4.0))
    assert total > 0.0


def test_apliquei_ignora_registro_antigo_ou_ja_confirmado():
    """
    O registro pendente só pode ser reaproveitado se for recente E ainda sem
    dose_aplicada — nunca um já confirmado antes, nem um velho demais (fora
    da janela de JANELA_APLIQUEI_MINUTOS), senão "apliquei" sobrescreveria
    silenciosamente um registro antigo não relacionado.
    """
    fake = FakeSupabase()
    bolus.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.store["registros_bolus"] = [
        # já confirmado há pouco -> não deve ser reaproveitado
        {
            "id": "antigo-confirmado", "usuario_id": usuario_id, "dose_aplicada": 3.0,
            "dose_calculada": 3.0, "glicemia_referencia": 140,
            "horario": (agora - timedelta(minutes=10)).isoformat(),
            "horario_aplicacao": (agora - timedelta(minutes=10)).isoformat(),
        },
        # pendente, mas calculado há muito tempo (fora da janela de 60min)
        {
            "id": "pendente-velho", "usuario_id": usuario_id, "dose_aplicada": None,
            "dose_calculada": 5.0, "glicemia_referencia": 200,
            "horario": (agora - timedelta(hours=5)).isoformat(),
        },
    ]

    registro = _executar(registrar_dose_aplicada(usuario_id, 8.0))

    # não deve ter mexido em nenhum dos dois antigos — criou um novo
    assert registro["id"] not in ("antigo-confirmado", "pendente-velho")
    assert registro["dose_aplicada"] == 8.0
    antigo = next(r for r in fake.store["registros_bolus"] if r["id"] == "antigo-confirmado")
    assert antigo["dose_aplicada"] == 3.0
    velho = next(r for r in fake.store["registros_bolus"] if r["id"] == "pendente-velho")
    assert velho["dose_aplicada"] is None


def test_apliquei_anexa_a_correcao_pendente_recente():
    fake = FakeSupabase()
    bolus.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    fake.store["registros_bolus"] = [
        {
            "id": "correcao-recente", "usuario_id": usuario_id, "dose_aplicada": None,
            "dose_calculada": 2.0, "glicemia_referencia": 201,
            "horario": (agora - timedelta(minutes=3)).isoformat(),
        },
    ]

    registro = _executar(registrar_dose_aplicada(usuario_id, 2.0))

    assert registro["id"] == "correcao-recente"
    assert registro["dose_aplicada"] == 2.0
    assert registro["horario_aplicacao"] is not None
    assert len(fake.store["registros_bolus"]) == 1  # não criou registro novo


# --------------------------------------------------------------------------
# registrar_dose_aplicada com horario_aplicacao explícito — registro
# retroativo pedido pelo usuário: "tomei 6u às 12:20, esqueci de avisar".
# --------------------------------------------------------------------------

def test_registrar_dose_aplicada_retroativa_usa_horario_informado():
    fake = FakeSupabase()
    bolus.supabase = fake
    usuario_id = str(uuid.uuid4())
    horario_passado = datetime.now(timezone.utc) - timedelta(hours=1, minutes=9)

    registro = _executar(registrar_dose_aplicada(usuario_id, 6.0, horario_passado))

    assert registro["dose_aplicada"] == 6.0
    assert registro["horario_aplicacao"] == horario_passado.isoformat()
    assert registro["horario"] == horario_passado.isoformat()

    # já devia ter decaído uma parte real da dose, não estar "recém aplicada"
    total = _executar(calcular_insulina_ativa(usuario_id, 4.0))
    assert 0.0 < total < 6.0


def test_registrar_dose_aplicada_retroativa_so_anexa_pendente_anterior_ao_horario():
    """
    Um registro retroativo (ex: aplicado às 12:20) não deve anexar numa
    correção pendente calculada DEPOIS desse horário (ex: 12:45) — só faz
    sentido anexar a algo que já existia antes do momento retroativo.
    """
    fake = FakeSupabase()
    bolus.supabase = fake
    usuario_id = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)
    horario_retroativo = agora - timedelta(hours=1, minutes=9)

    fake.store["registros_bolus"] = [
        {
            "id": "calculo-depois-do-retroativo", "usuario_id": usuario_id, "dose_aplicada": None,
            "dose_calculada": 5.0, "glicemia_referencia": 200,
            "horario": (horario_retroativo + timedelta(minutes=25)).isoformat(),
        },
    ]

    registro = _executar(registrar_dose_aplicada(usuario_id, 6.0, horario_retroativo))

    assert registro["id"] != "calculo-depois-do-retroativo"
    pendente = next(r for r in fake.store["registros_bolus"] if r["id"] == "calculo-depois-do-retroativo")
    assert pendente["dose_aplicada"] is None
