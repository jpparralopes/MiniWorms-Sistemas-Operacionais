from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import queue
import socket
import threading

from jogo import Partida
from motor import executar_motor

MAX_MENSAGEM = 4096


class Servidor:
    def __init__(self, host: str, port: int):
        self.host, self.port = host, port
        contexto = mp.get_context('spawn')
        self.memoria = contexto.Array('i', Partida().lista(), lock=False)
        self.mutex = contexto.Lock()
        self.comandos = contexto.Queue()
        self.eventos = contexto.Queue()
        self.motor = contexto.Process(target=executar_motor,
                                args=(self.memoria, self.mutex, self.comandos, self.eventos),
                                name='MiniWormsMotor')
        self.clientes: dict[int, socket.socket] = {}
        self.clientes_mutex = threading.Lock()
        self.locks_envio: dict[int, threading.Lock] = {}
        self.ativo = True

    def estado(self) -> dict:
        with self.mutex:
            return Partida.da_lista(self.memoria[:]).publico()

    def escrever_marca(self, jogador: int) -> bool:
        with self.mutex:
            partida = Partida.da_lista(self.memoria[:])
            if partida.fase != 1:
                return False
            self.memoria[Partida.CAMPOS.index('marca')] = jogador
            print(f'[MEMÓRIA] Servidor gravou {"X" if jogador == 1 else "Y"}', flush=True)
        return True

    @staticmethod
    def enviar(conn: socket.socket, mensagem: dict):
        pacote = (json.dumps(mensagem, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')
        conn.sendall(pacote)

    def enviar_jogador(self, jogador: int, mensagem: dict):
        with self.clientes_mutex:
            conn = self.clientes.get(jogador)
            lock = self.locks_envio.get(jogador)
        if conn and lock:
            try:
                with lock:
                    self.enviar(conn, mensagem)
            except OSError:
                pass

    def publicar(self):
        while self.ativo:
            try:
                evento = self.eventos.get(timeout=0.2)
            except queue.Empty:
                continue
            destino, payload = evento['destino'], evento['payload']
            if payload.get('type') == 'SHOT':
                atual = self.estado()
                print(f'[MEMÓRIA COMPARTILHADA] Disparos={atual["disparos"]} | '
                      f'HP1={atual["hp1"]} | HP2={atual["hp2"]} | '
                      f'Turno={atual["turno"]}', flush=True)
            if destino:
                self.enviar_jogador(destino, payload)
            else:
                for j in (1, 2):
                    self.enviar_jogador(j, payload)

    def atender(self, conn: socket.socket, jogador: int):
        try:
            self.enviar_jogador(jogador, {'type': 'WELCOME', 'player': jogador})
            self.comandos.put({'jogador': jogador, 'acao': {'type': 'CONEXAO', 'online': True}})
            print(f'[REDE] Jogador {jogador} entrou.', flush=True)
            with conn.makefile('r', encoding='utf-8', newline='\n') as entrada:
                for linha in entrada:
                    if len(linha) > MAX_MENSAGEM:
                        self.enviar_jogador(jogador, {'type': 'ERROR', 'message': 'Mensagem muito grande.'})
                        break
                    try:
                        pacote = json.loads(linha)
                        if not isinstance(pacote, dict):
                            raise ValueError('JSON não é um objeto')
                    except (json.JSONDecodeError, ValueError):
                        self.enviar_jogador(jogador, {'type': 'ERROR', 'message': 'JSON inválido.'})
                        continue
                    if pacote.get('type') == 'PING':
                        self.enviar_jogador(jogador, {'type': 'PONG'})
                        continue
                    if pacote.get('type') == 'MARK':
                        if self.escrever_marca(jogador):
                            self.comandos.put({'jogador': jogador, 'acao': {'type': 'READ_MARK'}})
                        else:
                            self.enviar_jogador(jogador, {'type': 'ERROR', 'message': 'Aguarde os dois jogadores.'})
                        continue
                    if pacote.get('type') not in ('MOVE', 'AIM', 'FIRE', 'RESTART'):
                        self.enviar_jogador(jogador, {'type': 'ERROR', 'message': 'Ação desconhecida.'})
                        continue
                    self.comandos.put({'jogador': jogador, 'acao': pacote})
        except (OSError, UnicodeError) as exc:
            print(f'[REDE] Jogador {jogador}: {exc}', flush=True)
        finally:
            with self.clientes_mutex:
                if self.clientes.get(jogador) is conn:
                    del self.clientes[jogador]
                    self.locks_envio.pop(jogador, None)
                    self.comandos.put({'jogador': jogador, 'acao': {'type': 'CONEXAO', 'online': False}})
            try:
                conn.close()
            except OSError:
                pass
            print(f'[REDE] Jogador {jogador} saiu.', flush=True)

    def iniciar(self):
        self.motor.start()
        threading.Thread(target=self.publicar, daemon=True, name='Eventos').start()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((self.host, self.port))
            servidor.listen(4)
            servidor.settimeout(0.5)
            print(f'[SERVIDOR] Pronto em {self.host}:{self.port}', flush=True)
            print('[SERVIDOR] Abra dois clientes. Ctrl+C encerra.', flush=True)
            try:
                while True:
                    try:
                        conn, addr = servidor.accept()
                    except socket.timeout:
                        continue
                    with self.clientes_mutex:
                        vagas = [j for j in (1, 2) if j not in self.clientes]
                        if not vagas:
                            self.enviar(conn, {'type': 'ERROR', 'message': 'Sala cheia (2 jogadores).'})
                            conn.close()
                            continue
                        jogador = vagas[0]
                        self.clientes[jogador] = conn
                        self.locks_envio[jogador] = threading.Lock()
                    threading.Thread(target=self.atender, args=(conn, jogador), daemon=True).start()
            except KeyboardInterrupt:
                print('\n[SERVIDOR] Encerrando...', flush=True)
            finally:
                self.ativo = False
                with self.clientes_mutex:
                    for conn in self.clientes.values():
                        try:
                            conn.shutdown(socket.SHUT_RDWR)
                            conn.close()
                        except OSError:
                            pass
                self.comandos.put(None)
                self.motor.join(timeout=3)
                if self.motor.is_alive():
                    self.motor.terminate()
                    self.motor.join(timeout=2)


def main():
    mp.freeze_support()
    p = argparse.ArgumentParser(description='Servidor de jogo Mini Worms')
    p.add_argument('--host', default='127.0.0.1', help='127.0.0.1 para local; 0.0.0.0 para rede local')
    p.add_argument('--port', type=int, default=5050)
    args = p.parse_args()
    Servidor(args.host, args.port).iniciar()


if __name__ == '__main__':
    main()