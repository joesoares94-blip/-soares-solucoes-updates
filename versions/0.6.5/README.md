# Soares Soluções 0.6.5

Correção urgente da tela de entrada da versão 0.6.4.

A captura do proprietário mostrou que o contorno do cartão permanecia centralizado, mas o formulário era deslocado para fora da janela. O frame já era posicionado por `relx=.5` e `rely=.5`; a atualização de tamanho adicionava `x=w/2` e `y=h/2`, duplicando os deslocamentos. A correção altera somente largura e altura ao redimensionar.

O login, a marca e a ilustração continuam no mesmo desenho. O banco de dados local, as movimentações e o histórico não são parte do pacote.

Verificado: sintaxe Python, geometria do painel da captura 1366×768 e correspondência SHA-256 dos arquivos do manifesto. A aplicação no Windows precisa ser confirmada após a atualização.
