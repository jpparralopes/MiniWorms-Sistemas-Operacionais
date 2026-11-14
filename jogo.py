from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin, radians, hypot, exp

LARGURA, ALTURA = 960, 520
GRAVIDADE = 0.47
RAIO_EXPLOSAO = 82
DANO_MAXIMO = 78
PASSO_MOVIMENTO = 24


def terreno_y(x: float) -> float:
    base = 400 + 26 * sin(x / 93) + 12 * sin(x / 37)
    morros = 30 * exp(-((x - 270) / 82) ** 2) + 36 * exp(-((x - 715) / 95) ** 2)
    vale = 66 * exp(-((x - 493) / 122) ** 2)
    return base - morros + vale


@dataclass
class Partida:
    x1: int = 130
    x2: int = 825
    hp1: int = 100
    hp2: int = 100
    turno: int = 1
    fase: int = 0
    vencedor: int = 0
    disparos: int = 0
    ang1: int = 45
    ang2: int = 45
    forca1: int = 80
    forca2: int = 80
    movimentos: int = 2
    conectado1: int = 0
    conectado2: int = 0
    marca: int = 0

    CAMPOS = ('x1', 'x2', 'hp1', 'hp2', 'turno', 'fase', 'vencedor',
              'disparos', 'ang1', 'ang2', 'forca1', 'forca2',
              'movimentos', 'conectado1', 'conectado2', 'marca')

    def lista(self) -> list[int]:
        return [getattr(self, campo) for campo in self.CAMPOS]

    @classmethod
    def da_lista(cls, dados):
        return cls(*list(dados))

    def publico(self):
        return {
            'x1': self.x1, 'x2': self.x2,
            'hp1': self.hp1, 'hp2': self.hp2,
            'turno': self.turno, 'fase': self.fase, 'vencedor': self.vencedor,
            'disparos': self.disparos, 'ang1': self.ang1, 'ang2': self.ang2,
            'forca1': self.forca1, 'forca2': self.forca2,
            'movimentos': self.movimentos,
            'conectado1': self.conectado1, 'conectado2': self.conectado2,
            'marca': self.marca,
        }


def simular_tiro(x: float, angulo: int, forca: int, direcao: int):
    vel = forca / 5.0
    vx = direcao * vel * cos(radians(angulo))
    vy = -vel * sin(radians(angulo))
    py = terreno_y(x) - 32
    px = x + direcao * 17
    trajeto = [[round(px, 1), round(py, 1)]]
    impacto = [px, py]
    for passo in range(1, 480):
        dt = 0.50
        px += vx * dt
        py += vy * dt
        vy += GRAVIDADE * dt
        if passo % 2 == 0:
            trajeto.append([round(px, 1), round(py, 1)])
        if px < 5 or px > LARGURA - 5:
            impacto = [max(5, min(LARGURA - 5, px)), py]
            break
        if py >= terreno_y(px) - 2 and passo > 6:
            impacto = [px, terreno_y(px) - 2]
            break
        if py > ALTURA + 100:
            impacto = [px, ALTURA]
            break
    else:
        impacto = [px, py]
    trajeto.append([round(impacto[0], 1), round(impacto[1], 1)])
    return trajeto, [round(impacto[0], 1), round(impacto[1], 1)]


def dano_explosao(impacto, x_alvo):
    distancia = hypot(impacto[0] - x_alvo, impacto[1] - (terreno_y(x_alvo) - 17))
    return max(0, round(DANO_MAXIMO * (1 - distancia / RAIO_EXPLOSAO)))


def aplicar_acao(partida: Partida, jogador: int, acao: dict):
    tipo = str(acao.get('type', '')).upper()
    if tipo == 'CONEXAO':
        conectado = int(bool(acao.get('online')))
        setattr(partida, f'conectado{jogador}', conectado)
        if partida.conectado1 and partida.conectado2:
            if partida.fase == 0:
                _reiniciar(partida)
        else:
            partida.fase = 0
        return {'type': 'STATE', 'state': partida.publico()}, None

    if tipo == 'RESTART':
        if partida.fase != 2:
            return None, 'Só é possível reiniciar uma partida encerrada.'
        if not (partida.conectado1 and partida.conectado2):
            return None, 'Ambos os jogadores precisam estar conectados.'
        _reiniciar(partida)
        return {'type': 'STATE', 'state': partida.publico()}, None

    if partida.fase != 1:
        return None, 'Aguarde os dois jogadores ou reinicie a partida.'
    if partida.turno != jogador:
        return None, 'Aguarde sua vez.'
    if tipo == 'MOVE':
        if partida.movimentos <= 0:
            return None, 'Você já utilizou os dois movimentos deste turno.'
        direcao = acao.get('dir')
        if type(direcao) is not int or direcao not in (-1, 1):
            return None, 'Direção inválida.'
        x_atual = partida.x1 if jogador == 1 else partida.x2
        adversario = partida.x2 if jogador == 1 else partida.x1
        novo_x = max(38, min(LARGURA - 38, x_atual + PASSO_MOVIMENTO * direcao))
        if abs(novo_x - adversario) < 52:
            return None, 'Muito perto do outro jogador.'
        setattr(partida, f'x{jogador}', novo_x)
        partida.movimentos -= 1
        return {'type': 'STATE', 'state': partida.publico()}, None
    if tipo == 'AIM':
        angulo, forca = acao.get('angle'), acao.get('power')
        if type(angulo) is not int or type(forca) is not int:
            return None, 'Ângulo e força devem ser números inteiros.'
        if not (15 <= angulo <= 85 and 35 <= forca <= 100):
            return None, 'Ângulo ou força fora dos limites.'
        setattr(partida, f'ang{jogador}', angulo)
        setattr(partida, f'forca{jogador}', forca)
        return {'type': 'STATE', 'state': partida.publico()}, None
    if tipo == 'FIRE':
        antes = partida.publico()
        x = getattr(partida, f'x{jogador}')
        direcao = 1 if jogador == 1 else -1
        trajeto, impacto = simular_tiro(x, getattr(partida, f'ang{jogador}'),
                                        getattr(partida, f'forca{jogador}'), direcao)
        dano1 = dano_explosao(impacto, partida.x1)
        dano2 = dano_explosao(impacto, partida.x2)
        partida.hp1 = max(0, partida.hp1 - dano1)
        partida.hp2 = max(0, partida.hp2 - dano2)
        partida.disparos += 1
        if partida.hp1 == 0 or partida.hp2 == 0:
            partida.fase = 2
            if partida.hp1 == 0 and partida.hp2 == 0:
                partida.vencedor = 3
            else:
                partida.vencedor = 1 if partida.hp2 == 0 else 2
        else:
            partida.turno = 2 if jogador == 1 else 1
            partida.movimentos = 2
        return {
            'type': 'SHOT', 'by': jogador, 'path': trajeto, 'impact': impacto,
            'damage': [dano1, dano2], 'before': antes, 'state': partida.publico(),
        }, None
    return None, 'Comando desconhecido.'


def _reiniciar(p: Partida):
    online1, online2 = p.conectado1, p.conectado2
    novo = Partida()
    for campo in p.CAMPOS:
        setattr(p, campo, getattr(novo, campo))
    p.conectado1, p.conectado2 = online1, online2
    p.fase = 1