from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from juridico_core import Store, audit_document, export_word, import_manual, missing_manuals, read_assignment, run_work


class FakeResearch:
    def __init__(self):
        self.calls = []

    def run_stage(self, stage, work, progress):
        self.calls.append(stage)
        source = {"title": "Fonte oficial", "url": "https://www.planalto.gov.br/lei"}
        content = ("1 DESCRIÇÃO DO CASO\n2.1 DECISÕES POSSÍVEIS\n2.2 ARGUMENTOS\n"
                   "3 CRITÉRIOS E VALORES\n4 CONCLUSÃO\nREFERÊNCIAS\n"
                   "https://www.planalto.gov.br/lei\n" + "Aplicação cuidadosa aos fatos. " * 80)
        return content, [source]


class LegalWorkspaceTests(unittest.TestCase):
    def test_independent_storage_pipeline_versions_and_docx(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "juridico.db")
            work_id = store.create("owner", "Caso demonstrativo", "case", "Fatos e perguntas do professor. " * 4)
            with self.assertRaises(ValueError):
                store.get("other", work_id)
            client = FakeResearch()
            finished = run_work(store, "owner", work_id, client)
            self.assertEqual(client.calls, ["juridico", "redacao", "revisao", "finalizacao"])
            self.assertEqual(finished["stage"], "concluido")
            self.assertEqual(finished["revision"], 1)
            self.assertEqual(len(finished["sources"]), 1)
            self.assertEqual(len(store.versions("owner", work_id)), 2)
            target = Path(folder) / "teste.docx"
            export_word(finished, target)
            self.assertIn("DESCRIÇÃO DO CASO", read_assignment(target))
            store.save_draft("owner", work_id, finished["draft"] + "\nRevisão.", expected=1)
            self.assertEqual(store.restore("owner", work_id, 1, 2), 3)
            self.assertEqual(store.get("owner", work_id)["draft"], finished["draft"])
            self.assertFalse((Path(folder) / "soares_solucoes.db").exists())

    def test_unregistered_url_is_flagged(self):
        report = audit_document("paper", "INTRODUÇÃO DESENVOLVIMENTO CONCLUSÃO REFERÊNCIAS "
                                "https://example.invalid/caso", [{"url": "https://tribunal.jus.br/real"}])
        self.assertEqual(report["status"], "pendencias")
        self.assertEqual(report["untracked_links"], ["https://example.invalid/caso"])

    def test_manuals_can_be_imported_locally_after_automatic_update(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"LOCALAPPDATA": folder}), \
             patch("juridico_core.resource", side_effect=lambda name: Path(folder)/"absent"/name), \
             patch("juridico_core.read_assignment", return_value="Conteúdo confirmado do manual. " * 60):
            self.assertEqual(len(missing_manuals()), 2)
            import_manual("manual_case_paper.txt", Path("MANUALDECASEEPAPER.pdf"))
            import_manual("manuals_cases.txt", Path("Cases.pdf"))
            self.assertEqual(missing_manuals(), [])


if __name__ == "__main__":
    unittest.main()
