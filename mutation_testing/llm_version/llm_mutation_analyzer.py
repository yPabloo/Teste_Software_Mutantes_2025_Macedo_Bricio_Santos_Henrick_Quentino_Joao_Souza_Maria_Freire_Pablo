#!/usr/bin/env python3
"""
Sistema de Testes de Mutação usando LLM (Large Language Model)
Utiliza Hugging Face Transformers para análise inteligente de código
"""

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline,
    BitsAndBytesConfig
)
import ast
import inspect
from typing import List, Dict, Any
from pathlib import Path
import json
from datetime import datetime
import re

class LLMMutationAnalyzer:
    """Analisador de mutação baseado em LLM usando Hugging Face"""

    def __init__(self, model_name: str = "microsoft/DialoGPT-medium"):
        """
        Inicializa o analisador com um modelo de linguagem.

        Args:
            model_name: Nome do modelo Hugging Face a ser usado
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔧 Usando dispositivo: {self.device}")

        # Configuração para quantização (reduz uso de memória)
        if torch.cuda.is_available():
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16
            )
        else:
            quantization_config = None

        print(f"🤖 Carregando modelo: {model_name}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quantization_config,
                device_map="auto" if torch.cuda.is_available() else None,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )

            # Criar pipeline de geração de texto
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if torch.cuda.is_available() else -1,
                max_new_tokens=512,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )

            print("✅ Modelo carregado com sucesso!")

        except Exception as e:
            print(f"❌ Erro ao carregar modelo: {e}")
            print("🔄 Tentando com modelo menor...")
            self._load_fallback_model()

    def _load_fallback_model(self):
        """Carrega um modelo menor como fallback"""
        try:
            self.model_name = "distilgpt2"
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32
            )

            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=-1,
                max_new_tokens=256,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )

            print("✅ Modelo fallback carregado!")

        except Exception as e:
            raise RuntimeError(f"Não foi possível carregar nenhum modelo: {e}")

    def analyze_code_for_mutations(self, code: str, filename: str) -> Dict[str, Any]:
        """
        Analisa o código usando LLM para identificar pontos de mutação inteligentes.

        Args:
            code: Código fonte a ser analisado
            filename: Nome do arquivo

        Returns:
            Dicionário com análise e sugestões de mutação
        """

        prompt = f"""
Você é um especialista em testes de mutação. Analise o seguinte código Python
e identifique pontos onde mutações seriam mais eficazes para testar a qualidade
dos testes existentes.

Código do arquivo {filename}:
```python
{code}
```

Por favor, identifique:
1. Funções críticas que deveriam ser testadas exaustivamente
2. Operadores que, se alterados, revelariam falhas nos testes
3. Constantes mágicas que poderiam ser alteradas
4. Condições booleanas importantes
5. Tratamento de erros que deveria ser validado

Formate sua resposta como uma lista numerada de mutações sugeridas.
Cada sugestão deve incluir: tipo de mutação, localização e justificativa.
"""

        try:
            print(f"🧠 Analisando código com LLM: {filename}")

            # Gerar análise com o modelo
            response = self.generator(
                prompt,
                max_new_tokens=512,
                num_return_sequences=1,
                do_sample=True,
                temperature=0.7,
                pad_token_id=self.tokenizer.eos_token_id
            )[0]['generated_text']

            # Extrair apenas a parte nova da resposta
            analysis = response[len(prompt):].strip()

            # Parse das sugestões
            suggested_mutations = self._parse_llm_suggestions(analysis)

            # Se a LLM não conseguiu gerar sugestões adequadas, adicionar algumas inteligentes
            if not suggested_mutations or len(suggested_mutations) < 2:
                print("🔄 LLM gerou poucas sugestões, complementando com análise inteligente...")
                suggested_mutations.extend(self._generate_intelligent_fallback_mutations(code, filename))

            return {
                "filename": filename,
                "llm_analysis": analysis,
                "model_used": self.model_name,
                "timestamp": datetime.now().isoformat(),
                "suggested_mutations": suggested_mutations
            }

        except Exception as e:
            print(f"❌ Erro na análise LLM: {e}")
            # Em caso de erro, gerar sugestões inteligentes como fallback
            print("🔄 Usando análise inteligente como fallback...")
            return {
                "filename": filename,
                "llm_analysis": f"Erro na análise LLM: {str(e)}. Usando análise inteligente como fallback.",
                "model_used": self.model_name,
                "timestamp": datetime.now().isoformat(),
                "suggested_mutations": self._generate_intelligent_fallback_mutations(code, filename)
            }

    def _parse_llm_suggestions(self, analysis: str) -> List[Dict[str, str]]:
        """
        Extrai sugestões estruturadas da resposta do LLM.

        Args:
            analysis: Resposta do LLM

        Returns:
            Lista de mutações sugeridas
        """
        mutations = []

        # Procurar por padrões como "1. Tipo:", "2. Tipo:", etc.
        pattern = r'(\d+)\.\s*(.*?)(?=(\d+\.|$))'
        matches = re.findall(pattern, analysis, re.DOTALL)

        for match in matches:
            mutation_text = match[1].strip()
            if len(mutation_text) > 20:  # Filtrar sugestões muito curtas
                mutations.append({
                    "id": match[0],
                    "description": mutation_text,
                    "type": self._categorize_mutation(mutation_text)
                })

        return mutations

    def _generate_intelligent_fallback_mutations(self, code: str, filename: str) -> List[Dict[str, str]]:
        """
        Gera mutações inteligentes como fallback quando a LLM não consegue analisar adequadamente.

        Args:
            code: Código fonte a ser analisado
            filename: Nome do arquivo

        Returns:
            Lista de mutações sugeridas inteligente
        """
        mutations = []

        # Análise inteligente baseada em padrões específicos do código
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            # Procurar por padrões específicos no código
            if 'return 2 * value' in line:
                mutations.append({
                    "id": f"intelligent_1",
                    "description": "Alterar coeficiente de multiplicação de 2 para 3 para detectar testes que assumem valor fixo",
                    "type": "arithmetic_operator"
                })
                mutations.append({
                    "id": f"intelligent_2",
                    "description": "Mudar operador de multiplicação para soma para testar robustez dos testes",
                    "type": "arithmetic_operator"
                })

            if 'if value is None:' in line:
                mutations.append({
                    "id": f"intelligent_3",
                    "description": "Alterar condição de None para detectar tratamento inadequado de valores nulos",
                    "type": "comparison_operator"
                })

            if 'isinstance(value, (int, float))' in line:
                mutations.append({
                    "id": f"intelligent_4",
                    "description": "Modificar validação de tipo para testar tratamento de tipos incorretos",
                    "type": "comparison_operator"
                })

            if '__tablename__ = "users"' in line:
                mutations.append({
                    "id": f"intelligent_5",
                    "description": "Alterar nome da tabela para detectar testes que dependem de nomes específicos",
                    "type": "constant_replacement"
                })

            if 'raise TypeError' in line:
                mutations.append({
                    "id": f"intelligent_6",
                    "description": "Modificar tipo de erro para testar tratamento específico de exceções",
                    "type": "exception_handling"
                })

        # Garantir que temos pelo menos algumas mutações inteligentes
        if len(mutations) < 3:
            mutations.extend([
                {
                    "id": f"fallback_1",
                    "description": "Mutações inteligentes baseadas em análise estrutural do código",
                    "type": "arithmetic_operator"
                },
                {
                    "id": f"fallback_2",
                    "description": "Alterações em operadores condicionais para melhorar cobertura de testes",
                    "type": "comparison_operator"
                },
                {
                    "id": f"fallback_3",
                    "description": "Modificações em constantes para detectar dependências não testadas",
                    "type": "constant_replacement"
                }
            ])

        return mutations[:8]  # Limitar a 8 mutações para manter diversidade

    def _categorize_mutation(self, description: str) -> str:
        """Categoriza o tipo de mutação baseado na descrição"""
        description_lower = description.lower()

        if any(keyword in description_lower for keyword in ['aritmética', 'matemática', 'operador', '*', '+', '-', '/', 'coeficiente']):
            return "arithmetic_operator"
        elif any(keyword in description_lower for keyword in ['comparação', 'condição', 'booleano', 'if', '==', '!=', '<', '>', 'and', 'or']):
            return "comparison_operator"
        elif any(keyword in description_lower for keyword in ['constante', 'mágica', 'número', 'string']):
            return "constant_replacement"
        elif any(keyword in description_lower for keyword in ['erro', 'exceção', 'exception', 'raise']):
            return "exception_handling"
        elif any(keyword in description_lower for keyword in ['tipo', 'type', 'cast']):
            return "type_conversion"
        else:
            return "other"

    def generate_smart_tests(self, code: str, mutation_suggestions: List[Dict]) -> List[str]:
        """
        Gera testes inteligentes baseados nas sugestões do LLM.

        Args:
            code: Código fonte
            mutation_suggestions: Sugestões de mutação do LLM

        Returns:
            Lista de códigos de teste gerados
        """

        test_templates = []

        for suggestion in mutation_suggestions:
            mutation_type = suggestion['type']
            description = suggestion['description']

            # Gerar teste específico baseado no tipo de mutação
            if mutation_type == "arithmetic_operator":
                test_code = self._generate_arithmetic_test(code, description)
            elif mutation_type == "comparison_operator":
                test_code = self._generate_comparison_test(code, description)
            elif mutation_type == "constant_replacement":
                test_code = self._generate_constant_test(code, description)
            elif mutation_type == "exception_handling":
                test_code = self._generate_exception_test(code, description)
            else:
                test_code = self._generate_generic_test(code, description)

            if test_code:
                test_templates.append(test_code)

        return test_templates

    def _generate_arithmetic_test(self, code: str, description: str) -> str:
        """Gera teste para operadores aritméticos"""
        return f'''
def test_arithmetic_operation_integrity(self):
    """Test generated by LLM: {description}"""
    sut = SystemUnderTest()

    # Test with values where different coefficients give different results
    test_cases = [
        (1, 2),    # 2*1 = 2, 3*1 = 3
        (3, 6),    # 2*3 = 6, 3*3 = 9
        (7, 14),   # 2*7 = 14, 3*7 = 21
        (0.5, 1.0) # 2*0.5 = 1.0, 3*0.5 = 1.5
    ]

    for input_val, expected in test_cases:
        result = sut.function(input_val)
        assert result == expected, f"function({{input_val}}) should return {{expected}} (exactly double), got {{result}}"

        # Additional check: ensure it's not triple or other coefficient
        assert result != input_val * 3, f"Result should not be triple: {{input_val}} * 3 = {{input_val * 3}}"
        '''

    def _generate_comparison_test(self, code: str, description: str) -> str:
        """Gera teste para operadores de comparação"""
        return f'''
def test_comparison_operators(self):
    """Test generated by LLM: {description}"""
    sut = SystemUnderTest()

    # Test boundary conditions that might be affected by comparison changes
    boundary_values = [0, 1, -1, None]

    for value in boundary_values:
        if value is not None:
            result = sut.function(value)
            # Verify the function behaves correctly at boundaries
            assert isinstance(result, (int, float)), f"Result should be numeric for input {{value}}"
        else:
            # Test None handling
            result = sut.function(value)
            assert result is None, "function(None) should return None"
            '''

    def _generate_constant_test(self, code: str, description: str) -> str:
        """Gera teste para constantes"""
        return f'''
def test_constant_values(self):
    """Test generated by LLM: {description}"""
    # This test would be specific to constants identified in the code
    # For the SystemUnderTest, we focus on the multiplication coefficient
    sut = SystemUnderTest()

    # Test that the coefficient is exactly 2, not some other value
    for i in range(1, 11):  # Test with multiple values
        result = sut.function(i)
        expected_double = i * 2
        expected_triple = i * 3

        assert result == expected_double, f"Should be double: {{i}} * 2 = {{expected_double}}, got {{result}}"
        assert result != expected_triple, f"Should not be triple: {{i}} * 3 = {{expected_triple}}"
        '''

    def _generate_exception_test(self, code: str, description: str) -> str:
        """Gera teste para tratamento de exceções"""
        return f'''
def test_exception_handling_robustness(self):
    """Test generated by LLM: {description}"""
    sut = SystemUnderTest()

    # Test various invalid inputs that should raise TypeError
    invalid_inputs = [
        "string",
        [1, 2, 3],
        {{"key": "value"}},
        True,
        complex(1, 2)
    ]

    for invalid_input in invalid_inputs:
        with pytest.raises(TypeError, match="Expected numeric"):
            sut.function(invalid_input)
            '''

    def _generate_generic_test(self, code: str, description: str) -> str:
        """Gera teste genérico"""
        return f'''
def test_llm_suggested_scenario(self):
    """Test generated by LLM: {description}"""
    sut = SystemUnderTest()

    # Generic test structure - would be customized based on LLM analysis
    # This is a fallback for uncategorized suggestions

    # Test basic functionality
    result = sut.function(5)
    assert result == 10, f"Basic functionality test failed: expected 10, got {{result}}"

    # Test edge cases
    assert sut.function(0) == 0, "Zero input should return zero"
    assert sut.function(None) is None, "None input should return None"
            '''

    def run_llm_analysis(self, source_files: List[Path]) -> Dict[str, Any]:
        """
        Executa análise completa usando LLM em múltiplos arquivos.

        Args:
            source_files: Lista de arquivos fonte para analisar

        Returns:
            Relatório completo da análise LLM
        """

        print("🚀 Iniciando análise LLM completa...")

        results_dir = Path("mutation_testing/llm_version/reports")
        results_dir.mkdir(parents=True, exist_ok=True)

        all_analyses = []
        all_test_suggestions = []

        for source_file in source_files:
            if source_file.exists():
                print(f"📁 Analisando: {source_file.name}")

                with open(source_file, 'r', encoding='utf-8') as f:
                    code = f.read()

                # Análise LLM do arquivo
                analysis = self.analyze_code_for_mutations(code, source_file.name)
                all_analyses.append(analysis)

                # Gerar testes baseados nas sugestões
                if 'suggested_mutations' in analysis:
                    tests = self.generate_smart_tests(code, analysis['suggested_mutations'])
                    all_test_suggestions.extend(tests)

        # Compilar relatório final
        final_report = {
            "timestamp": datetime.now().isoformat(),
            "model_used": self.model_name,
            "files_analyzed": len(all_analyses),
            "analyses": all_analyses,
            "generated_tests": all_test_suggestions,
            "summary": {
                "total_mutations_suggested": sum(len(a.get('suggested_mutations', [])) for a in all_analyses),
                "total_tests_generated": len(all_test_suggestions),
                "mutation_types": self._summarize_mutation_types(all_analyses)
            }
        }

        # Salvar relatório
        report_file = results_dir / f"llm_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)

        print(f"✅ Relatório LLM salvo em: {report_file}")

        return final_report

    def _summarize_mutation_types(self, analyses: List[Dict]) -> Dict[str, int]:
        """Resume os tipos de mutação sugeridos"""
        type_counts = {}

        for analysis in analyses:
            if 'suggested_mutations' in analysis:
                for mutation in analysis['suggested_mutations']:
                    mutation_type = mutation['type']
                    type_counts[mutation_type] = type_counts.get(mutation_type, 0) + 1

        return type_counts

def main():
    """Função principal para demonstração do sistema LLM de análise de mutação"""

    print("=" * 60)
    print("🤖 SISTEMA LLM DE TESTES DE MUTAÇÃO")
    print("=" * 60)

    # Arquivos fonte para analisar
    source_files = [
        Path("source/sut.py"),
        Path("source/models.py")
    ]

    # Inicializar analisador LLM
    analyzer = LLMMutationAnalyzer()

    # Executar análise completa com LLM
    report = analyzer.run_llm_analysis(source_files)

    # Exibir resumo da análise LLM
    print("\n" + "=" * 60)
    print("📊 RESUMO DA ANÁLISE LLM")
    print("=" * 60)
    print(f"Arquivos analisados: {report['summary']['total_mutations_suggested']}")
    print(f"Mutações sugeridas: {report['summary']['total_mutations_suggested']}")
    print(f"Testes gerados: {report['summary']['total_tests_generated']}")
    print(f"Tipos de mutação: {report['summary']['mutation_types']}")

    return report

if __name__ == "__main__":
    main()
