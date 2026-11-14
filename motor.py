from __future__ import annotations

from jogo import Partida, aplicar_acao


def executar_motor(memoria, mutex, entrada, saida):
    print('[MOTOR] Processo independente iniciado; memória compartilhada ativa.', flush=True)
    while True:
        comando = entrada.get()
        if comando is None:
            break
        jogador = comando['jogador']
        with mutex:
            atual = Partida.da_lista(memoria[:])
            if comando['acao'].get('type') == 'READ_MARK':
                evento, erro = {'type': 'STATE', 'state': atual.publico()}, None
                print(f'[MEMÓRIA] Motor leu {"X" if atual.marca == 1 else "Y"}', flush=True)
            else:
                evento, erro = aplicar_acao(atual, jogador, comando['acao'])
                if erro is None:
                    memoria[:] = atual.lista()
        if erro:
            saida.put({'destino': jogador, 'payload': {'type': 'ERROR', 'message': erro}})
        elif evento:
            saida.put({'destino': 0, 'payload': evento})
    print('[MOTOR] Encerrado.', flush=True)