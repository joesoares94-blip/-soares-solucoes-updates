# Soares Soluções 0.5.7 — Estúdio Jurídico

Este módulo aparece no menu do programa Windows existente após o login de Proprietário.
Os dados jurídicos ficam em `%LOCALAPPDATA%\Soares Solucoes\Juridico\trabalhos.db`.
O banco de estoque não é alterado.

O atualizador do programa usa `update.json`: baixa cada arquivo de `versions/0.5.7`,
verifica SHA-256 e substitui os arquivos da aplicação ao reiniciar. O manifesto
só deve chegar à ramificação principal após validar a interface no Windows.

Na primeira abertura, use **Importar manuais FACSUR** e selecione os dois PDFs
recebidos no curso. Os textos extraídos são guardados apenas no computador.
Os PDFs e seus textos integrais não foram publicados neste repositório público.
O usuário pode informar a chave de API para a sessão; ela não é salva no banco.

Verificações realizadas: fluxo local com respostas simuladas, separação por
usuário, restauração de revisões, leitura de PDF com dependência incluída e
renderização do Word preliminar. Ainda faltam teste da janela no Windows,
pesquisa real com chave de API e modelos `.docx` de Case e Paper.
