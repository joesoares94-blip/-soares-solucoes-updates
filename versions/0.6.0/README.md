# Soares Soluções 0.6.0

Interface baseada na prévia aprovada pelo proprietário, com monograma SS.

- Menu azul com ícones, painel claro, cartões e cantos arredondados.
- Dashboard e catálogo com pesquisa, filtros, ordenação e paginação.
- Alertas de estoque baixo (1 a 5 unidades) e estoque zerado.
- Movimentações recentes extraídas do banco local.
- Campos nativos de texto dentro de bordas independentes: desenho e edição não compartilham métodos.
- Cadastro de produto com rolagem e rodapé fixo.
- Sem módulo jurídico; nenhuma alteração no esquema ou no conteúdo do banco.

## Verificações

Testado com Tk em display virtual Linux, com banco temporário isolado:
- abertura de Dashboard, Produtos, Inventário, Movimentações, Histórico, Usuários e Atualizações;
- digitação, seleção, exclusão de texto e redimensionamento dos campos;
- navegação em 1366×728 e 1120×660;
- cadastro de mercadoria por clique no botão;
- transferência de estoque e conferência dos saldos;
- exportação PDF;
- ocultação das ações restritas no perfil Consulta.

A renderização usa Segoe UI no Windows. O teste em display virtual verifica comportamento e layout,
mas não substitui a validação final no Windows.

Distribuição: o manifesto público lista app.py, modern_ui.py, modern_shell.py e brand_logo.png,
com os respectivos hashes SHA-256, além dos arquivos já usados pela instalação.
