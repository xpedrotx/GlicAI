from app.services import crise


def test_detectar_risco_reconhece_frases_diretas():
    assert crise.detectar_risco("eu quero morrer")
    assert crise.detectar_risco("Quero Me Matar hoje")
    assert crise.detectar_risco("nao aguento mais viver assim")
    assert crise.detectar_risco("acho que vou me suicidar")


def test_detectar_risco_ignora_acentuacao_e_maiusculas():
    assert crise.detectar_risco("NÃO AGUENTO MAIS VIVER")
    assert crise.detectar_risco("Não Vejo Sentido Em Viver mais")


def test_detectar_risco_nao_dispara_pra_mensagens_normais_de_diabetes():
    assert not crise.detectar_risco("glicemia 173")
    assert not crise.detectar_risco("bolus 40g 130")
    assert not crise.detectar_risco("não aguento mais essa fome, quando vou comer")
    assert not crise.detectar_risco("oi, tudo bem?")
    assert not crise.detectar_risco("ajuda")


def test_mensagem_apoio_traz_cvv_e_samu():
    texto = crise.mensagem_apoio()
    assert "188" in texto
    assert "192" in texto
    assert "cvv" in texto.lower()
