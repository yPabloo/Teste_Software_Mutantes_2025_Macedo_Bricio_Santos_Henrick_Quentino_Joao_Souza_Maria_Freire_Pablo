"""
Novos testes criados especificamente para detectar mutantes sobreviventes
identificados na primeira rodada de testes de mutação.
"""

import pytest
from source import SystemUnderTest
from source.models import User


class TestMutationDetection:
    """Testes específicos para detectar mutantes sobreviventes."""

    @pytest.mark.parametrize("input_value, expected_double", [
        (0, 0),
        (1, 2),
        (2, 4),
        (5, 10),
        (-1, -2),
        (0.5, 1.0),
        (10.5, 21.0),
    ])
    def test_function_returns_exactly_double(self, input_value, expected_double):
        """
        Testa especificamente que a função retorna exatamente o dobro do valor.

        Este teste visa detectar mutantes que alterem o coeficiente de multiplicação.
        Por exemplo, se um mutante alterar 'return 2 * value' para 'return 3 * value',
        este teste irá falhar porque 3 * 1 = 3, mas esperamos 2.
        """
        sut = SystemUnderTest()
        result = sut.function(input_value)
        assert result == expected_double, f"function({input_value}) should return {expected_double}, got {result}"

    def test_function_coefficient_is_exactly_two(self):
        """
        Teste específico para verificar que o coeficiente é exatamente 2.

        Este teste usa uma abordagem diferente para detectar mudanças no coeficiente.
        """
        sut = SystemUnderTest()

        # Teste com valor específico onde 2x e 3x dão resultados diferentes
        result_2x = sut.function(3)  # 2 * 3 = 6
        result_3x = 9  # 3 * 3 = 9

        # Se o mutante mudou para 3x, result_2x seria 9, não 6
        assert result_2x == 6, f"function(3) should be 6 (2*3), got {result_2x}"
        assert result_2x != result_3x, "Coefficient should be exactly 2, not 3"

    def test_function_with_none_input(self):
        """Testa que a função retorna None quando recebe None."""
        sut = SystemUnderTest()
        result = sut.function(None)
        assert result is None, "function(None) should return None"

    def test_function_with_invalid_type_raises_error(self):
        """Testa que a função lança TypeError para tipos inválidos."""
        sut = SystemUnderTest()

        with pytest.raises(TypeError, match="Expected numeric"):
            sut.function("invalid")

        with pytest.raises(TypeError, match="Expected numeric"):
            sut.function([1, 2, 3])


class TestModelMutationDetection:
    """Testes específicos para detectar mutantes no modelo User."""

    def test_user_table_name_is_correct(self):
        """
        Testa que o nome da tabela do modelo User está correto.

        Este teste visa detectar mutantes que alterem o nome da tabela,
        como '__tablename__ = "users"' para '__tablename__ = "usuarios"'.
        """
        expected_table_name = "users"
        actual_table_name = User.__tablename__

        assert actual_table_name == expected_table_name, \
            f"User table name should be '{expected_table_name}', got '{actual_table_name}'"

    def test_user_has_required_columns(self):
        """
        Testa que o modelo User possui todas as colunas necessárias.
        """
        # Verificar colunas obrigatórias
        required_columns = ['id', 'first_name', 'created_at']

        for column_name in required_columns:
            assert hasattr(User, column_name), f"User model should have column '{column_name}'"

    def test_user_id_is_primary_key(self):
        """
        Testa que a coluna 'id' é a chave primária.
        """
        id_column = User.id
        assert id_column.primary_key, "User.id should be the primary key"

    def test_user_column_types(self):
        """
        Testa que as colunas têm os tipos corretos.
        """
        # Verificar tipos das colunas
        assert str(User.id.type) == "INTEGER", f"User.id should be INTEGER, got {User.id.type}"
        assert "VARCHAR" in str(User.first_name.type), f"User.first_name should be VARCHAR, got {User.first_name.type}"
        assert "DATETIME" in str(User.created_at.type), f"User.created_at should be DATETIME, got {User.created_at.type}"


class TestEdgeCases:
    """Testes para casos extremos que podem revelar mutantes."""

    def test_function_with_very_large_numbers(self):
        """Testa a função com números muito grandes."""
        sut = SystemUnderTest()

        large_number = 1000000
        result = sut.function(large_number)
        expected = large_number * 2

        assert result == expected, f"function({large_number}) should return {expected}, got {result}"

    def test_function_with_very_small_numbers(self):
        """Testa a função com números muito pequenos."""
        sut = SystemUnderTest()

        small_number = 0.000001
        result = sut.function(small_number)
        expected = small_number * 2

        assert result == expected, f"function({small_number}) should return {expected}, got {result}"

    def test_function_with_zero(self):
        """Testa a função com zero."""
        sut = SystemUnderTest()

        result = sut.function(0)
        expected = 0

        assert result == expected, f"function(0) should return {expected}, got {result}"
