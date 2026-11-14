# Mini Worms — Batalha 1v1

Jogo de artilharia 2D para dois jogadores. Trabalho 02 de Sistemas Operacionais (ESOFT-4S).

## Iniciar uma partida

1. Extraia os arquivos para uma pasta.
2. Execute `MiniWorms.exe` (depois de gerar o arquivo) ou `INICIAR_DEMO_WINDOWS.bat`.

Alternativa, em três terminais abertos na pasta:

```cmd
py -3 servidor.py
py -3 cliente.py
py -3 cliente.py
```

## Como jogar

- Cada personagem começa com 100 HP.
- O jogo inicia com os dois clientes conectados.
- O jogador da vez pode mover até duas vezes, usando `A` e `D` ou os botões.
- Ajuste o ângulo de 15° a 85° e a força de 35% a 100%.
- Use `Espaço` ou `ATIRAR` para disparar.
- Pressione `M` ou `MARCAR` para trocar a bandeira compartilhada entre `X` e `Y` (disponível para os dois jogadores).
- O projétil tem trajetória parabólica; a explosão pode causar dano aos dois jogadores.
- A rodada termina quando um jogador fica sem vida. Use `R` para reiniciar.

## Arquitetura

Os dois clientes comunicam-se com o servidor por **sockets TCP**, usando mensagens JSON. O servidor envia os comandos ao motor por `multiprocessing.Queue`. O motor é um processo independente, responsável por validar os movimentos, calcular os tiros e atualizar a partida.

O servidor e o motor compartilham um `multiprocessing.Array` protegido por `multiprocessing.Lock`. A tecla `M` (ou o botão `MARCAR`) demonstra a leitura e a escrita nessa memória: o Jogador 1 grava `X`, o Jogador 2 substitui por `Y`, e o motor lê o resultado. Os clientes visualizam a alteração por mensagens TCP; não acessam diretamente a memória do computador servidor.

Para demonstrar: com os dois jogadores conectados, pressione `M` na janela do Jogador 1 para mostrar `X` e depois `M` na janela do Jogador 2 para substituir por `Y`. As duas telas serão atualizadas.

## Partida em rede local

No computador que hospeda o servidor:

```cmd
py -3 servidor.py --host 0.0.0.0 --port 5050
```

Nos computadores dos jogadores (trocar pelo IP local do servidor):

```cmd
py -3 cliente.py --host 192.168.1.10 --port 5050
```

## Limites do jogo

Uma sala de dois jogadores, uma arma, sem autenticação ou acesso pela internet pública. A água é um elemento visual do cenário.

## Executável e entrega

Execute `GERAR_ENTREGA_WINDOWS.bat` para criar o `MiniWorms.exe` e os dois ZIPs da entrega na pasta `ENTREGA`. O executável é um iniciador leve do projeto Python, não um empacotamento do interpretador: precisa de Python 3 instalado no computador e dos arquivos `.py` ao lado. Ele abre o mesmo servidor e os dois clientes do script de demonstração. Os ZIPs não incluem executáveis PyInstaller antigos.