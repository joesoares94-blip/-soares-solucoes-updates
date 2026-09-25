# Soares Soluções 0.6.2

Inclui a identidade visual e a tela de acesso da versão 0.6.1.

Correções operacionais:
- Ajustes de inventário são registrados mesmo quando o total não muda. O histórico mostra os saldos anteriores e posteriores, com usuário responsável.
- Transferências e ajustes bloqueiam a escrita antes de ler o saldo, evitando que operações simultâneas movimentem a mesma unidade.
- Cadastro, estoque inicial e histórico são gravados em uma única transação.
- Entrada em produto inexistente é recusada.
- Histórico com nomes em português, detalhes e rolagem. A tela informa o limite de 300 registros exibidos; os demais permanecem no banco.

Validação executada em banco temporário isolado, sem acessar dados do cliente:
- Interface Tk: entrada no depósito, entrada na exposição, transferências em ambos os sentidos e ajuste de inventário.
- Persistência: processos separados antes/depois da troca de services.py, com reinicialização do catálogo original. Saldos e seis registros preservados.
- Concorrência: duas transferências de uma unidade com saldo de uma unidade; apenas uma aceita.
- Falha forçada ao gravar histórico: estoque e cadastro integralmente revertidos.
- Quantidades inválidas recusadas; verificação de integridade e chaves estrangeiras aprovada.

Ambiente: Linux/Python/Tk/Xvfb. O instalador e a aplicação das atualizações no Windows não foram executados neste ambiente.

Armazenamento atual: SQLite local em %LOCALAPPDATA%/Soares Solucoes/soares_solucoes.db no Windows. Não há envio de movimentações para nuvem, sincronização entre computadores ou backup remoto automático. A atualização automática distribui arquivos do programa, não dados dos clientes.
