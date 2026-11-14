from __future__ import annotations

import argparse
import json
import math
import queue
import socket
import threading
import time
import tkinter as tk

from jogo import Partida, LARGURA, ALTURA, terreno_y, simular_tiro

FUNDO = '#0b1222'
PAINEL = '#14203a'
BORDA = '#2a3c59'
TEXTO = '#f2f7ff'
APAGADO = '#a6bad5'
VERDE = '#8aebc2'
AMARELO = '#f9d581'
ROSA = '#ff839c'
AZUL = '#7ba7ff'


class ClienteRede:
    def __init__(self, host: str, porta: int, eventos: queue.Queue):
        self.host, self.porta, self.eventos = host, porta, eventos
        self.conn = None
        self.mutex = threading.Lock()
        self.ativo = True
        threading.Thread(target=self.conectar, name='RedeCliente', daemon=True).start()

    def conectar(self):
        try:
            self.conn = socket.create_connection((self.host, self.porta), timeout=6)
            self.conn.settimeout(None)
            self.eventos.put({'type': 'CONNECTED'})
            with self.conn.makefile('r', encoding='utf-8', newline='\n') as entrada:
                for linha in entrada:
                    try:
                        dado = json.loads(linha)
                        if isinstance(dado, dict):
                            self.eventos.put(dado)
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:
            self.eventos.put({'type': 'ERROR', 'message': f'Conexão: {exc}'})
        finally:
            self.ativo = False
            self.eventos.put({'type': 'DISCONNECTED'})

    def enviar(self, dado):
        with self.mutex:
            if not self.ativo or not self.conn:
                return False
            try:
                self.conn.sendall((json.dumps(dado, separators=(',', ':')) + '\n').encode('utf-8'))
                return True
            except OSError:
                self.eventos.put({'type': 'DISCONNECTED'})
                return False

    def fechar(self):
        self.ativo = False
        if self.conn:
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.conn.close()
            except OSError:
                pass


class MiniWormsApp:
    def __init__(self, raiz, host='127.0.0.1', porta=5050):
        self.raiz = raiz
        self.raiz.title('MINI WORMS | Batalha 1v1')
        self.raiz.configure(bg=FUNDO)
        self.raiz.geometry('1004x762')
        self.raiz.minsize(1004, 762)
        self.raiz.resizable(False, False)
        self.jogador = 0
        self.partida = Partida().publico()
        self.mira_angulo = tk.IntVar(value=45)
        self.mira_forca = tk.IntVar(value=80)
        self.eventos = queue.Queue()
        self.animacao = None
        self.inicio_animacao = 0.0
        self.aviso_ate = 0.0
        self.status = tk.StringVar(value='Conectando ao servidor...')
        self.precisa_redesenhar = True
        self._estado_controles = None

        self._criar_interface()
        self.rede = ClienteRede(host, porta, self.eventos)
        self.raiz.bind('<KeyPress-a>', lambda e: self.mover(-1))
        self.raiz.bind('<KeyPress-d>', lambda e: self.mover(1))
        self.raiz.bind('<KeyPress-space>', lambda e: self.atirar())
        self.raiz.bind('<KeyPress-r>', lambda e: self.reiniciar())
        self.raiz.bind('<KeyPress-m>', lambda e: self.marcar())
        self.raiz.protocol('WM_DELETE_WINDOW', self.fechar)
        self._atualizar()

    def _label(self, pai, texto, tamanho=10, cor=TEXTO, negrito=False):
        return tk.Label(pai, text=texto, bg=pai.cget('bg'), fg=cor,
                        font=('Segoe UI', tamanho, 'bold' if negrito else 'normal'))

    def _botao(self, pai, texto, comando, cor=PAINEL, letra=TEXTO, largura=10):
        return tk.Button(pai, text=texto, command=comando,
                         bg=cor, fg=letra, activebackground=BORDA, activeforeground='white',
                         font=('Segoe UI', 10, 'bold'), bd=0, relief='flat',
                         cursor='hand2', padx=12, pady=8, width=largura)

    def _criar_interface(self):
        barra = tk.Frame(self.raiz, bg=FUNDO, height=64)
        barra.pack(fill='x', padx=22)
        barra.pack_propagate(False)
        tk.Label(barra, text='MINI', bg=FUNDO, fg=TEXTO,
                 font=('Segoe UI', 20, 'bold')).pack(side='left', pady=12)
        tk.Label(barra, text='WORMS', bg=FUNDO, fg=VERDE,
                 font=('Segoe UI', 20, 'bold')).pack(side='left', pady=12)
        tk.Label(barra, text='  |  BATALHA 1V1', bg=FUNDO, fg=APAGADO,
                 font=('Segoe UI', 9, 'bold')).pack(side='left', pady=15)
        tk.Label(barra, text='BATALHA POR TURNOS', bg=FUNDO, fg=APAGADO,
                 font=('Segoe UI', 9, 'bold')).pack(side='right', pady=15)

        contorno = tk.Frame(self.raiz, bg=BORDA, padx=2, pady=2)
        contorno.pack(padx=20)
        self.canvas = tk.Canvas(contorno, width=LARGURA, height=ALTURA,
                                bg='#b9e4f5', highlightthickness=0)
        self.canvas.pack()
        self._pintar_fundo()

        info = tk.Frame(self.raiz, bg=FUNDO, height=42)
        info.pack(fill='x', padx=24)
        self._label(info, 'STATUS:', 9, APAGADO, True).pack(side='left', pady=12)
        tk.Label(info, textvariable=self.status, bg=FUNDO, fg=VERDE,
                 font=('Segoe UI', 10)).pack(side='left', padx=10, pady=12)
        self._label(info, 'A / D: MOVER  ·  ESPAÇO: ATIRAR  ·  R: REINICIAR',
                    9, APAGADO).pack(side='right')

        controles = tk.Frame(self.raiz, bg=PAINEL, padx=16, pady=13)
        controles.pack(fill='x', padx=20)
        lado_esq = tk.Frame(controles, bg=PAINEL)
        lado_esq.pack(side='left', anchor='n')
        self._label(lado_esq, 'MOVIMENTO', 10, APAGADO, True).pack(anchor='w')
        linha = tk.Frame(lado_esq, bg=PAINEL)
        linha.pack(pady=(9, 0))
        self.btn_esq = self._botao(linha, '◀ ESQ', lambda: self.mover(-1), largura=8)
        self.btn_esq.pack(side='left', padx=(0, 7))
        self.btn_dir = self._botao(linha, 'DIR ▶', lambda: self.mover(1), largura=8)
        self.btn_dir.pack(side='left')
        self._label(lado_esq, '2 movimentos por turno', 9, APAGADO).pack(anchor='w', pady=(7, 0))

        meio = tk.Frame(controles, bg=PAINEL)
        meio.pack(side='left', padx=(29, 0), anchor='n')
        self._label(meio, 'MIRA DA BAZUCA', 10, APAGADO, True).pack(anchor='w')
        self.rotulo_angulo = self._label(meio, 'ÂNGULO: 45°', 9, TEXTO)
        self.rotulo_angulo.pack(anchor='w', pady=(4, 0))
        self.escala_angulo = tk.Scale(meio, from_=15, to=85, variable=self.mira_angulo,
                                      orient='horizontal', length=230, bg=PAINEL, fg=TEXTO,
                                      activebackground=VERDE, troughcolor='#314563',
                                      highlightthickness=0, showvalue=False, bd=0,
                                      command=lambda v: self._mira_local())
        self.escala_angulo.pack()
        self.escala_angulo.bind('<ButtonRelease-1>', lambda e: self.enviar_mira())

        lado_dir = tk.Frame(controles, bg=PAINEL)
        lado_dir.pack(side='left', padx=(22, 0), anchor='n')
        self._label(lado_dir, 'FORÇA DO DISPARO', 10, APAGADO, True).pack(anchor='w')
        self.rotulo_forca = self._label(lado_dir, 'FORÇA: 80%', 9, TEXTO)
        self.rotulo_forca.pack(anchor='w', pady=(4, 0))
        self.escala_forca = tk.Scale(lado_dir, from_=35, to=100, variable=self.mira_forca,
                                     orient='horizontal', length=194, bg=PAINEL, fg=TEXTO,
                                     activebackground=AMARELO, troughcolor='#314563',
                                     highlightthickness=0, showvalue=False, bd=0,
                                     command=lambda v: self._mira_local())
        self.escala_forca.pack()
        self.escala_forca.bind('<ButtonRelease-1>', lambda e: self.enviar_mira())

        acao = tk.Frame(controles, bg=PAINEL)
        acao.pack(side='right', padx=(12, 0), anchor='n')
        self._label(acao, 'AÇÃO', 10, APAGADO, True).pack(anchor='w')
        self.btn_fogo = self._botao(acao, 'ATIRAR!', self.atirar, cor=ROSA,
                                   letra='#211623', largura=10)
        self.btn_fogo.pack(pady=(8, 0))
        botoes = tk.Frame(acao, bg=PAINEL)
        botoes.pack(pady=(6, 0))
        self.btn_marca = self._botao(botoes, 'MARCAR', self.marcar, largura=6)
        self.btn_marca.pack(side='left', padx=(0, 5))
        self.btn_restart = self._botao(botoes, 'REINICIAR', self.reiniciar, largura=7)
        self.btn_restart.pack(side='left')
        self._alterar_controles()

    def _pintar_fundo(self):
        c = self.canvas
        cor_ini = (171, 219, 243)
        cor_fim = (238, 247, 252)
        for y in range(0, ALTURA, 3):
            t = y / ALTURA
            cor = '#%02x%02x%02x' % tuple(round(a*(1-t)+b*t) for a,b in zip(cor_ini, cor_fim))
            c.create_rectangle(0, y, LARGURA, y+3, fill=cor, outline=cor)
        c.create_oval(777, 41, 850, 114, fill='#fff1ae', outline='')
        for x,y,s in [(93,77,1),(302,103,.68),(533,56,.83),(829,148,.70)]:
            for dx,dy,r in [(-34,9,22),(-5,0,29),(25,9,22)]:
                c.create_oval(x+(dx-r)*s,y+(dy-r)*s,x+(dx+r)*s,y+(dy+r)*s,
                              fill='#f6fbff', outline='')
        c.create_polygon(0,330,145,215,310,329,473,238,618,338,792,214,960,335,
                         960,520,0,520, fill='#a2cbd3', outline='')
        c.create_polygon(0,373,127,281,292,369,502,280,676,375,865,288,960,357,
                         960,520,0,520, fill='#8fbbc2', outline='')
        c.create_polygon(0,379,180,296,366,382,510,313,681,389,827,307,960,371,
                         960,520,0,520, fill='#84b1b2', outline='')
        pontos = []
        for x in range(0, LARGURA+1, 7):
            pontos.extend((x, terreno_y(x)))
        c.create_polygon(*pontos, LARGURA, ALTURA, 0, ALTURA,
                         fill='#947055', outline='')
        c.create_line(*pontos, fill='#6eb385', width=14, smooth=True)
        c.create_line(*pontos, fill='#b8d49a', width=4, smooth=True)
        nivel_agua = 429
        lago = [x for x in range(421, 602, 4) if terreno_y(x) > nivel_agua]
        for x in lago:
            fundo = terreno_y(x)
            c.create_rectangle(x, nivel_agua, x + 5, fundo,
                               fill='#3d9fbb', outline='')
            c.create_line(x, nivel_agua + 3, x + 5, nivel_agua + 3,
                          fill='#8fe6e6', width=2)
        for x in (472, 494, 517, 544, 565):
            if terreno_y(x) > nivel_agua:
                c.create_arc(x - 12, nivel_agua - 4, x + 12, nivel_agua + 3,
                             start=180, extent=180, style='arc', outline='#d0ffff', width=2)
        for x in (214, 242, 275, 327, 674, 711, 754, 796):
            y = terreno_y(x)
            c.create_line(x, y-2, x-4, y-10, fill='#376c4b', width=2)
            c.create_line(x, y-2, x+5, y-13, fill='#2a854d', width=2)
            c.create_oval(x-3, y-18, x+3, y-12, fill='#e9c875', outline='')
        for x in (366, 640, 893):
            y = terreno_y(x)
            c.create_oval(x-17, y-4, x+17, y+8,
                          fill='#8a8678', outline='#67675d', width=2)
            c.create_line(x-9, y-1, x+7, y-1, fill='#c7baa5', width=2)
        for i in range(52):
            x = (i*137+54) % 957
            y = min(ALTURA-10, terreno_y(x)+23+(i*23)%67)
            c.create_oval(x,y,x+5,y+3,fill='#b6956c', outline='')
        c.create_rectangle(0,0,LARGURA,47,fill='#15243a',outline='')
        c.create_line(0,47,LARGURA,47,fill='#2f485e',width=2)

    def _desenhar_marca(self):
        c = self.canvas
        x, y = 499, 426
        marca = self.partida.get('marca', 0)
        c.create_line(x, y, x, y - 55, fill='#473d34', width=4, tags='dinamico')
        cor = ROSA if marca == 1 else AZUL if marca == 2 else '#d3dce9'
        texto = 'X' if marca == 1 else 'Y' if marca == 2 else '?'
        c.create_polygon(x+2, y-53, x+43, y-45, x+2, y-27,
                         fill=cor, outline='#304660', width=2, tags='dinamico')
        c.create_text(x+16, y-44, text=texto, fill='#13253a',
                      font=('Segoe UI', 12, 'bold'), tags='dinamico')

    def _desenhar_personagem(self, x, hp, numero, destaque=False):
        c = self.canvas
        y = terreno_y(x)-16
        cor = ROSA if numero == 1 else AZUL
        tag = 'dinamico'
        c.create_oval(x-23,y+13,x+23,y+22, fill='#5d735b',outline='',tags=tag)
        c.create_oval(x-17,y-16,x+17,y+19,fill=cor,outline='#354862',width=2,tags=tag)
        c.create_oval(x-10,y-23,x+10,y-9,fill=cor,outline='#354862',width=1,tags=tag)
        for dx in (-7,5):
            c.create_oval(x+dx-1,y-12,x+dx+5,y-4,fill='white',outline='',tags=tag)
            c.create_oval(x+dx+2,y-9,x+dx+4,y-6,fill='#26334a',outline='',tags=tag)
        c.create_arc(x-7,y-2,x+8,y+9,start=195,extent=150,style='arc',outline='#27374a',width=2,tags=tag)
        c.create_oval(x-16,y+12,x-3,y+23,fill='#35475b',outline='',tags=tag)
        c.create_oval(x+3,y+12,x+16,y+23,fill='#35475b',outline='',tags=tag)
        angulo = (self.mira_angulo.get() if numero == self.jogador and self.sua_vez()
                  else self.partida['ang1' if numero == 1 else 'ang2'])
        rad = math.radians(angulo)
        direcao = 1 if numero == 1 else -1
        px,py=x+direcao*10,y-7
        c.create_line(px,py,px+direcao*25*math.cos(rad),py-25*math.sin(rad),
                      fill='#35465b',width=8,capstyle='round',tags=tag)
        c.create_line(px,py,px+direcao*25*math.cos(rad),py-25*math.sin(rad),
                      fill='#f7ce7e',width=4,capstyle='round',tags=tag)
        c.create_rectangle(x-34,y-49,x+34,y-43, fill='#3d4553',outline='',tags=tag)
        c.create_rectangle(x-34,y-49,x-34+68*hp/100,y-43,
                           fill='#73dca2' if hp>35 else '#fb816f',outline='',tags=tag)
        if destaque:
            c.create_oval(x-22,y-35,x+22,y+27,outline='#fff4a7',width=2,tags=tag)
        c.create_text(x,y-58,text='P'+str(numero),font=('Segoe UI',11,'bold'),
                      fill='#f9fcff' if destaque else '#eef4fe',tags=tag)

    def _desenhar_hud(self):
        c = self.canvas
        p = self.partida
        c.create_text(22,24,anchor='w',text=f'P1  |  {p["hp1"]:3} HP',
                      fill=ROSA,font=('Segoe UI',14,'bold'),tags='dinamico')
        c.create_text(LARGURA-22,24,anchor='e',text=f'P2  |  {p["hp2"]:3} HP',
                      fill=AZUL,font=('Segoe UI',14,'bold'),tags='dinamico')
        if p['fase']==0:
            mensagem='AGUARDANDO OS DOIS JOGADORES'
        elif p['fase']==2:
            mensagem=('EMPATE!' if p['vencedor']==3 else f'JOGADOR {p["vencedor"]} VENCEU!')
        else:
            mensagem=f'VEZ DO JOGADOR {p["turno"]}   ·   {p["movimentos"]} MOVIMENTOS'
        c.create_text(LARGURA/2,24,text=mensagem,fill=TEXTO,
                      font=('Segoe UI',12,'bold'),tags='dinamico')
        if self.jogador:
            cor = ROSA if self.jogador==1 else AZUL
            c.create_rectangle(15,61,178,91,fill='#182c42',outline='#314b63',tags='dinamico')
            c.create_text(28,76,text=f'VOCÊ É O JOGADOR {self.jogador}',anchor='w',
                          fill=cor,font=('Segoe UI',10,'bold'),tags='dinamico')
        c.create_rectangle(LARGURA-224, 61, LARGURA-15, 98,
                           fill='#182c42', outline='#314b63', tags='dinamico')
        c.create_rectangle(LARGURA-214, 69, LARGURA-189, 90,
                           fill='#294b4b', outline='#76caa5', tags='dinamico')
        c.create_text(LARGURA-201, 79, text='M', fill=VERDE,
                      font=('Segoe UI', 10, 'bold'), tags='dinamico')
        c.create_text(LARGURA-181, 73, anchor='nw', text='MARCAR BANDEIRA',
                      fill=TEXTO, font=('Segoe UI', 9, 'bold'), tags='dinamico')
        c.create_text(LARGURA-181, 88, anchor='nw', text='P1: X   |   P2: Y',
                      fill=APAGADO, font=('Segoe UI', 8), tags='dinamico')

    def _desenhar_mira(self):
        if not self.sua_vez() or self.animacao or self.jogador not in (1,2):
            return
        p=self.partida
        x=p['x1'] if self.jogador==1 else p['x2']
        direcao=1 if self.jogador==1 else -1
        a=math.radians(self.mira_angulo.get())
        y=terreno_y(x)-32
        c=self.canvas
        xx=x+direcao*(17+58*math.cos(a))
        yy=y-58*math.sin(a)
        c.create_line(x+direcao*17,y,xx,yy,fill='#fff9cc',width=3,dash=(7,5),tags='dinamico')
        c.create_oval(xx-5,yy-5,xx+5,yy+5,outline='#fff9cc',width=2,tags='dinamico')

    def _desenhar_animacao(self):
        if not self.animacao:
            return
        anim = self.animacao
        caminho = anim['path']
        passou = max(0, time.monotonic() - self.inicio_animacao)
        duracao_voo = (len(caminho) - 1) / 105.0
        c = self.canvas
        tags = ('dinamico', 'explosao')

        if passou < duracao_voo:
            indice = min(len(caminho) - 1, int(passou * 105))
            for px, py in caminho[max(0, indice - 17):indice:2]:
                c.create_oval(px-3, py-3, px+3, py+3,
                              fill='#fce8a8', outline='', tags=tags)
            px, py = caminho[indice]
            c.create_oval(px-6, py-6, px+6, py+6,
                          fill='#293b4c', outline='#f9cf6c', width=2, tags=tags)
            return

        progresso = min(1.0, (passou - duracao_voo) / 0.38)
        cx, cy = anim['impact']
        raio = 10 + 58 * math.sin(math.pi * progresso)
        c.create_oval(cx-raio, cy-raio, cx+raio, cy+raio,
                      outline='#ffb96d', width=max(1, round(5*(1-progresso))),
                      tags=tags)
        brilho = max(0, 19 * (1-progresso))
        if brilho > 1:
            c.create_oval(cx-brilho, cy-brilho, cx+brilho, cy+brilho,
                          fill='#ffe6a0', outline='#fff4c7', tags=tags)
        for i in range(8):
            a = (2 * math.pi * i / 8) + 0.3
            d = (11 + 60 * progresso)
            px, py = cx + d * math.cos(a), cy + d * math.sin(a)
            r = max(1, 4*(1-progresso))
            c.create_oval(px-r, py-r, px+r, py+r,
                          fill='#ffd47d', outline='', tags=tags)

    def _concluir_animacao(self):
        if not self.animacao:
            return
        estado_final = self.animacao['state']
        self.animacao = None
        self.canvas.delete('explosao')
        self.partida = estado_final
        self._ajustar_mira_servidor()
        self.precisa_redesenhar = True
        if self.partida['fase'] == 2:
            self.status.set('Partida encerrada. Clique em REINICIAR ou pressione R.')
        else:
            self.status.set('Disparo concluído. Próximo turno!')

    def _desenhar(self):
        self.canvas.delete('dinamico')
        self._desenhar_personagem(self.partida['x1'],self.partida['hp1'],1,
                                 self.partida['turno']==1 and self.partida['fase']==1)
        self._desenhar_personagem(self.partida['x2'],self.partida['hp2'],2,
                                 self.partida['turno']==2 and self.partida['fase']==1)
        self._desenhar_mira()
        self._desenhar_marca()
        self._desenhar_animacao()
        self._desenhar_hud()

    def sua_vez(self):
        return (self.jogador!=0 and self.partida['fase']==1
                and self.partida['turno']==self.jogador)

    def _alterar_controles(self):
        habilitado = self.sua_vez() and not self.animacao
        reiniciar = self.partida['fase'] == 2
        marcar = self.jogador in (1, 2) and self.partida['fase'] == 1 and not self.animacao
        estado_atual = (habilitado, reiniciar, marcar)
        if estado_atual == self._estado_controles:
            return
        self._estado_controles = estado_atual
        estado = tk.NORMAL if habilitado else tk.DISABLED
        for controle in (self.btn_esq, self.btn_dir, self.btn_fogo,
                         self.escala_angulo, self.escala_forca):
            controle.config(state=estado)
        self.btn_restart.config(state=tk.NORMAL if reiniciar else tk.DISABLED)
        self.btn_marca.config(state=tk.NORMAL if marcar else tk.DISABLED)

    def _mira_local(self):
        self.rotulo_angulo.config(text=f'ÂNGULO: {self.mira_angulo.get()}°')
        self.rotulo_forca.config(text=f'FORÇA: {self.mira_forca.get()}%')
        self.precisa_redesenhar = True

    def _ajustar_mira_servidor(self):
        if not self.jogador or self.jogador not in (1,2):
            return
        self.mira_angulo.set(self.partida[f'ang{self.jogador}'])
        self.mira_forca.set(self.partida[f'forca{self.jogador}'])
        self._mira_local()

    def enviar_mira(self):
        if self.sua_vez() and not self.animacao:
            self.rede.enviar({'type':'AIM','angle':self.mira_angulo.get(),
                              'power':self.mira_forca.get()})

    def mover(self, direcao):
        if self.sua_vez() and not self.animacao:
            self.rede.enviar({'type':'MOVE','dir':direcao})

    def atirar(self):
        if self.sua_vez() and not self.animacao:
            self.enviar_mira()
            self.rede.enviar({'type':'FIRE'})

    def marcar(self):
        if self.jogador in (1, 2) and self.partida['fase'] == 1 and not self.animacao:
            self.rede.enviar({'type': 'MARK'})

    def reiniciar(self):
        if self.partida['fase']==2:
            self.rede.enviar({'type':'RESTART'})

    def _receber(self, mensagem):
        tipo=mensagem.get('type')
        if tipo=='WELCOME':
            self.jogador=mensagem['player']
            self.status.set(f'Conectado como Jogador {self.jogador}. Aguardando adversário...')
            self._ajustar_mira_servidor()
        elif tipo=='STATE':
            anterior=self.partida
            novo=mensagem['state']
            if self.animacao:
                self.animacao['state']['marca'] = novo.get('marca', 0)
                return
            self.partida=novo
            if anterior.get('marca') != novo.get('marca') and novo.get('marca') in (1, 2):
                self.status.set('Bandeira compartilhada: ' + ('X' if novo['marca'] == 1 else 'Y'))
            if (anterior['turno']!=novo['turno'] or anterior['fase']!=novo['fase']):
                self._ajustar_mira_servidor()
            if novo['fase']==0:
                self.status.set('Aguardando o segundo jogador...')
            elif novo['fase']==2:
                self.status.set('Fim da partida. Pressione R para jogar novamente.')
            elif novo['turno']==self.jogador:
                self.status.set('Sua vez! Use A/D, ajuste a mira e atire.')
            else:
                self.status.set('Aguardando jogada do adversário...')
        elif tipo=='SHOT':
            if self.animacao:
                return
            self.partida=mensagem['before']
            self.animacao=mensagem
            self.inicio_animacao=time.monotonic()
            self.status.set(f'Jogador {mensagem["by"]} disparou!')
        elif tipo=='ERROR':
            self.status.set('AVISO: '+str(mensagem.get('message','Erro desconhecido')))
            self.aviso_ate=time.monotonic()+4
        elif tipo=='DISCONNECTED':
            self.status.set('Desconectado. Verifique se o servidor está executando.')
            self.jogador=0

    def _atualizar(self):
        houve_evento = False
        for _ in range(32):
            try:
                item = self.eventos.get_nowait()
            except queue.Empty:
                break
            self._receber(item)
            houve_evento = True

        if self.animacao:
            duracao_voo = (len(self.animacao['path']) - 1) / 105.0
            if time.monotonic() - self.inicio_animacao >= duracao_voo + 0.38:
                self._concluir_animacao()
                houve_evento = True

        if houve_evento or self.precisa_redesenhar or self.animacao:
            self.precisa_redesenhar = False
            self._desenhar()
            self._alterar_controles()
        self.raiz.after(25 if self.animacao else 80, self._atualizar)

    def fechar(self):
        self.rede.fechar()
        self.raiz.destroy()


def main():
    p=argparse.ArgumentParser(description='Cliente gráfico Mini Worms')
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=5050)
    args=p.parse_args()
    root=tk.Tk()
    MiniWormsApp(root,args.host,args.port)
    root.mainloop()


if __name__=='__main__':
    main()