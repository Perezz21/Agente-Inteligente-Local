"""Testes estruturais do conjunto adicional de dez cenários."""

import json
import unittest
from pathlib import Path

from src.executar_experimentos import carregar_cenarios


RAIZ = Path(__file__).resolve().parents[1]
EXPANSAO = RAIZ / "experiments" / "cenarios_expansao_05_14.json"
PILOTO = RAIZ / "experiments" / "cenarios_piloto.json"


class TesteCatalogoExpandido(unittest.TestCase):
    def test_01_dez_cenarios_com_ids_esperados(self):
        cenarios = carregar_cenarios(EXPANSAO)
        self.assertEqual(
            [c["id"] for c in cenarios],
            [f"cenario_{numero:02d}" for numero in range(5, 15)],
        )

    def test_02_sem_resultados_de_referencia_inventados(self):
        cenarios = carregar_cenarios(EXPANSAO)
        self.assertTrue(all(
            c["resultado_esperado"] is None for c in cenarios
        ))

    def test_03_ids_sem_colisao_com_piloto(self):
        piloto = carregar_cenarios(PILOTO)
        novos = carregar_cenarios(EXPANSAO)
        ids_piloto = {c["id"] for c in piloto}
        ids_novos = {c["id"] for c in novos}
        self.assertFalse(ids_piloto & ids_novos)

    def test_04_agregacoes_explicitamente_estruturadas(self):
        raw = json.loads(EXPANSAO.read_text(encoding="utf-8"))
        agregados = [c for c in raw if c["requisicao"]["agregacoes"]]
        self.assertEqual(len(agregados), 3)
        self.assertEqual(
            {item["requisicao"]["agregacoes"][0]["funcao"] for item in agregados},
            {"AVG", "MAX"},
        )
        for caso in agregados:
            for agregado in caso["requisicao"]["agregacoes"]:
                self.assertIn(
                    agregado["campo"],
                    {"medicoes.nivel_m", "medicoes.vazao_m3_s"},
                )

    def test_05_variedade_e_estrutura_dos_cenarios(self):
        raw = json.loads(EXPANSAO.read_text(encoding="utf-8"))
        self.assertTrue(all(
            isinstance(c.get("categoria"), str) and c["categoria"].strip()
            for c in raw
        ))
        self.assertTrue(any(
            c["requisicao"]["agrupamento"] for c in raw
        ))
        self.assertTrue(any(
            not c["requisicao"]["filtros"] for c in raw
        ))
        self.assertTrue(any(
            c["requisicao"].get("filtros", {}).get("ano") == 2025
            for c in raw
        ))


if __name__ == "__main__":
    unittest.main()
