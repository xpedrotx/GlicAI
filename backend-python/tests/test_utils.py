from app.utils import validar_cpf


def test_validar_cpf_aceita_cpf_valido_sem_pontuacao():
    assert validar_cpf("11144477735") is True


def test_validar_cpf_aceita_cpf_valido_com_pontuacao():
    assert validar_cpf("111.444.777-35") is True


def test_validar_cpf_rejeita_digito_verificador_errado():
    assert validar_cpf("11144477734") is False


def test_validar_cpf_rejeita_sequencia_de_digitos_iguais():
    # "111.111.111-11" passa no cálculo do dígito verificador mas nunca é
    # um CPF real — precisa ser rejeitado explicitamente.
    assert validar_cpf("11111111111") is False


def test_validar_cpf_rejeita_tamanho_errado():
    assert validar_cpf("123456789") is False
    assert validar_cpf("123456789012") is False


def test_validar_cpf_rejeita_vazio_ou_none():
    assert validar_cpf("") is False
    assert validar_cpf(None) is False
