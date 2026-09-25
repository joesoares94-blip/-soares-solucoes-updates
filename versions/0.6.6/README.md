# Soares Soluções 0.6.6

- Nova arte do interior de um depósito cobre toda a metade esquerda do login, com recorte central responsivo e sem redução por vizinho mais próximo. A logo e a paleta azul existentes permanecem.
- Cantos de botões, campos, cartões e moldura de acesso passam a usar transparência suavizada em PNG gerado apenas com a biblioteca padrão; o botão de entrada também recebe degradê suavizado.
- No Windows, o processo solicita escala de DPI do sistema para evitar ampliação borrada. Em monitores Full HD, a janela usa até 1920 pixels de largura e a altura disponível, respeitando a barra de tarefas. Monitores menores continuam com a geometria anterior.
- Os arquivos de usuários, produtos, banco de dados e movimentações não fazem parte do manifesto de atualização.

Verificação: sintaxe Python, hashes SHA-256 do manifesto, dimensões e transparência das imagens PNG. A renderização e a autenticação devem ser verificadas na instalação Windows do usuário.

Arte gerada para esta versão: interior realista de um depósito organizado, estantes e caixas ocupando todo o quadro, luz e paleta azul marinho/cobalto, sem pessoas, textos, marcas ou interface. Gerada pela ferramenta integrada de imagens e otimizada para PNG compatível com Tkinter.
