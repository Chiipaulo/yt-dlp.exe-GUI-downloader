# Versão: 2026-10-07 - 12h36

import json
import os
import re
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime, timedelta
from io import BytesIO

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def obter_pasta_atual():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class DownloaderYouTubePro:

    def __init__(self, root):
        self.root = root
        self.root.title(
            "Downloader YouTube (AAC / M4A / MP4) - Versão 2026.10.07 12h36 - @paulochii"
        )
        self.root.geometry("1152x700")
        self.root.minsize(1008, 640)

        # Configurações de diretórios
        pasta_base = obter_pasta_atual()
        self.pasta_auxiliar = os.path.join(pasta_base, "auxiliar")
        self.pasta_downloads = os.path.join(pasta_base, "Downloads")
        self.arquivo_controle = os.path.join(
            self.pasta_auxiliar, "controle_atualizacao.json"
        )
        self.arquivo_config = os.path.join(
            self.pasta_auxiliar, "config_ytdlp.json"
        )

        if not os.path.exists(self.pasta_auxiliar):
            os.makedirs(self.pasta_auxiliar, exist_ok=True)
        if not os.path.exists(self.pasta_downloads):
            os.makedirs(self.pasta_downloads, exist_ok=True)

        os.environ["PATH"] += os.pathsep + self.pasta_auxiliar
        self.caminho_ytdlp = os.path.join(self.pasta_auxiliar, "yt-dlp.exe")

        # Variáveis de Estado
        self.config = self.carregar_config()
        pasta_salva = self.config.get("saida", self.pasta_downloads)
        self.pasta_destino = tk.StringVar(value=pasta_salva)

        self.formato_escolhido = tk.IntVar(value=1)  # 1: MP4, 2: M4A/AAC, 3: Ambos
        self.processo_atual = None
        self.download_cancelado = False

        self.vars_videos = []
        self.checkbuttons_videos = []

        self.criar_interface()

        # Início das verificações em Thread separada
        threading.Thread(
            target=self.rotina_inicial_atualizacao, daemon=True
        ).start()

    # --- CONFIGURAÇÃO E PERSISTÊNCIA ---
    def carregar_config(self):
        if os.path.exists(self.arquivo_config):
            try:
                with open(self.arquivo_config, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def salvar_config(self):
        try:
            with open(self.arquivo_config, "w", encoding="utf-8") as f:
                json.dump(
                    {"saida": self.pasta_destino.get()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

    # --- ATUALIZAÇÕES AUTOMÁTICAS E MANUAIS ---
    def rotina_inicial_atualizacao(self):
        self.escrever_log("Atualizando Programas...")

        controle = {}
        if os.path.exists(self.arquivo_controle):
            try:
                with open(self.arquivo_controle, "r", encoding="utf-8") as f:
                    controle = json.load(f)
            except Exception:
                controle = {}

        hoje = datetime.now()
        hoje_str = hoje.strftime("%Y-%m-%d")
        ultima_ytdlp = controle.get("ultima_atualizacao_ytdlp", "")
        ultima_demais = controle.get("ultima_atualizacao_demais", "")

        # 1. Atualização do yt-dlp.exe (uma vez por dia)
        if ultima_ytdlp == hoje_str:
            self.escrever_log("yt-dlp Atualizado.")
        else:
            self.escrever_log(
                "Verificando atualizações do yt-dlp na pasta 'auxiliar'..."
            )
            if os.path.exists(self.caminho_ytdlp):
                try:
                    subprocess.run(
                        [self.caminho_ytdlp, "-U"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.escrever_log(
                        "yt-dlp verificado e atualizado com sucesso!"
                    )
                    controle["ultima_atualizacao_ytdlp"] = hoje_str
                except Exception as e:
                    self.escrever_log(f"Aviso: Falha ao atualizar yt-dlp: {e}")
            else:
                self.escrever_log(
                    "ERRO: 'yt-dlp.exe' não foi localizado em 'auxiliar/'."
                )

        # 2. Atualização dos demais executáveis (ciclo de 30 dias)
        necessita_atualizacao_demais = False
        if not ultima_demais:
            necessita_atualizacao_demais = True
        else:
            try:
                data_demais = datetime.strptime(ultima_demais, "%Y-%m-%d")
                if hoje - data_demais >= timedelta(days=30):
                    necessita_atualizacao_demais = True
            except ValueError:
                necessita_atualizacao_demais = True

        if necessita_atualizacao_demais:
            self.escrever_log(
                "Ciclo de 30 dias: Verificando integridade dos executáveis auxiliares (FFmpeg/Deno)..."
            )
            self.executar_verificacao_executaveis_auxiliares(controle, hoje_str)
        else:
            self.escrever_log(
                f"Executáveis atualizados (Última checagem: {ultima_demais})."
            )

        # Salvar histórico de controle
        try:
            with open(self.arquivo_controle, "w", encoding="utf-8") as f:
                json.dump(controle, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        self.escrever_log("-" * 60)
        self.root.after(0, self.estado_botoes_ocioso)

    def iniciar_atualizacao_outros(self):
        self.btn_atualizar_outros.config(state=tk.DISABLED, bg="grey")
        threading.Thread(
            target=self.processar_atualizacao_outros, daemon=True
        ).start()

    def processar_atualizacao_outros(self):
        self.escrever_log("\n=== INICIANDO ATUALIZAÇÃO MANUAL DOS EXECUTÁVEIS AUXILIARES ===")
        hoje_str = datetime.now().strftime("%Y-%m-%d")

        controle = {}
        if os.path.exists(self.arquivo_controle):
            try:
                with open(self.arquivo_controle, "r", encoding="utf-8") as f:
                    controle = json.load(f)
            except Exception:
                controle = {}

        self.executar_verificacao_executaveis_auxiliares(controle, hoje_str)

        try:
            with open(self.arquivo_controle, "w", encoding="utf-8") as f:
                json.dump(controle, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        self.escrever_log("=== ATUALIZAÇÃO DOS EXECUTÁVEIS CONCLUÍDA ===\n")
        self.root.after(0, self.estado_botoes_ocioso)

    def executar_verificacao_executaveis_auxiliares(self, controle, hoje_str):
        executaveis_aux = ["ffmpeg.exe", "ffprobe.exe", "deno.exe"]
        encontrados = []
        ausentes = []

        for exe in executaveis_aux:
            caminho_exe = os.path.join(self.pasta_auxiliar, exe)
            if os.path.exists(caminho_exe):
                encontrados.append(exe)
                if exe == "deno.exe":
                    try:
                        self.escrever_log("Verificando/Atualizando Deno via repositório...")
                        res = subprocess.run(
                            [caminho_exe, "upgrade"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                            encoding="utf-8",
                            errors="replace",
                        )
                        if res.stdout:
                            for linha in res.stdout.strip().split("\n"):
                                if linha:
                                    self.escrever_log(f"  [Deno] {linha}")
                    except Exception as e:
                        self.escrever_log(f"  [Deno] Status: {e}")
                else:
                    try:
                        res = subprocess.run(
                            [caminho_exe, "-version"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                            encoding="utf-8",
                            errors="replace",
                        )
                        primeira_linha = res.stdout.split("\n")[0] if res.stdout else "OK"
                        self.escrever_log(f"  [{exe}] OK -> {primeira_linha[:50]}...")
                    except Exception:
                        self.escrever_log(f"  [{exe}] OK (Executável presente)")
            else:
                ausentes.append(exe)

        if ausentes:
            self.escrever_log(
                f"Aviso: Os seguintes executáveis não foram encontrados em 'auxiliar/': {', '.join(ausentes)}"
            )

        controle["ultima_atualizacao_demais"] = hoje_str

    # --- INTERFACE GRÁFICA (RESPONSIVA) ---
    def criar_interface(self):
        # Grid Principal
        self.root.columnconfigure(0, weight=1, minsize=520)
        self.root.columnconfigure(1, weight=1, minsize=480)
        self.root.rowconfigure(0, weight=1)

        # Coluna Esquerda
        self.coluna_esq = tk.Frame(self.root, padx=8, pady=8)
        self.coluna_esq.grid(row=0, column=0, sticky="nsew")

        # Coluna Direita
        self.coluna_dir = tk.Frame(self.root, padx=8, pady=8)
        self.coluna_dir.grid(row=0, column=1, sticky="nsew")

        # 1. URL
        frame_link = tk.LabelFrame(
            self.coluna_esq, text=" URL do Vídeo ou Playlist ", padx=8, pady=8
        )
        frame_link.pack(fill="x", pady=4)

        self.entry_link = tk.Entry(
            frame_link, font=("Segoe UI", 10), state=tk.DISABLED
        )
        self.entry_link.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 4))

        self.btn_colar = tk.Button(
            frame_link,
            text="Colar e Extrair",
            command=self.colar_e_extrair,
            state=tk.DISABLED,
            font=("Segoe UI", 9),
        )
        self.btn_colar.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_previa = tk.Button(
            frame_link,
            text="Buscar Prévia",
            command=self.iniciar_previa,
            bg="#2196F3",
            fg="white",
            state=tk.DISABLED,
            font=("Segoe UI", 9, "bold"),
        )
        self.btn_previa.pack(side=tk.LEFT)

        # 2. Prévia
        self.frame_previa = tk.LabelFrame(
            self.coluna_esq, text=" Prévia do Vídeo ", padx=8, pady=8
        )
        self.frame_previa.pack(fill="x", pady=4)

        self.lbl_imagem = tk.Label(
            self.frame_previa,
            text="Aguardando atualização...",
            width=28,
            height=7,
            bg="#E0E0E0",
        )
        self.lbl_imagem.pack(side=tk.LEFT, padx=(0, 8))

        frame_info = tk.Frame(self.frame_previa)
        frame_info.pack(side=tk.LEFT, fill="both", expand=True)

        self.lbl_titulo = tk.Label(
            frame_info,
            text="Título: -",
            wraplength=260,
            justify="left",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_titulo.pack(anchor="nw", pady=(4, 2))

        self.lbl_duracao = tk.Label(
            frame_info, text="Duração: -", fg="#555555", font=("Segoe UI", 9)
        )
        self.lbl_duracao.pack(anchor="nw")

        # 3. Opções e Formatos
        frame_opcoes = tk.LabelFrame(
            self.coluna_esq, text=" Formato de Download ", padx=8, pady=8
        )
        frame_opcoes.pack(fill="x", pady=4)

        self.rb_video = tk.Radiobutton(
            frame_opcoes,
            text="Vídeo+Áudio (MP4/AAC)",
            variable=self.formato_escolhido,
            value=1,
            state=tk.DISABLED,
        )
        self.rb_video.pack(side=tk.LEFT, padx=4)

        self.rb_audio = tk.Radiobutton(
            frame_opcoes,
            text="Áudio (M4A/AAC)",
            variable=self.formato_escolhido,
            value=2,
            state=tk.DISABLED,
        )
        self.rb_audio.pack(side=tk.LEFT, padx=4)

        self.rb_ambos = tk.Radiobutton(
            frame_opcoes,
            text="Ambos (MP4 + M4A)",
            variable=self.formato_escolhido,
            value=3,
            state=tk.DISABLED,
        )
        self.rb_ambos.pack(side=tk.LEFT, padx=4)

        # 4. Local de Salvamento
        frame_pasta = tk.LabelFrame(
            self.coluna_esq, text=" Local de Salvamento ", padx=8, pady=8
        )
        frame_pasta.pack(fill="x", pady=4)

        self.entry_pasta = tk.Entry(
            frame_pasta,
            textvariable=self.pasta_destino,
            font=("Segoe UI", 9),
            state=tk.DISABLED,
        )
        self.entry_pasta.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 4))

        self.btn_procurar = tk.Button(
            frame_pasta,
            text="Procurar...",
            command=self.escolher_pasta,
            state=tk.DISABLED,
        )
        self.btn_procurar.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_abrir_pasta = tk.Button(
            frame_pasta,
            text="Abrir Pasta",
            command=self.abrir_pasta,
            bg="#4CAF50",
            fg="white",
            state=tk.DISABLED,
        )
        self.btn_abrir_pasta.pack(side=tk.LEFT, padx=(0, 4))

        # BOTÃO SOLICITADO: Atualizar Executáveis (Amarelo, posicionado entre "Abrir Pasta" e "CANCELAR")
        self.btn_atualizar_outros = tk.Button(
            frame_pasta,
            text="Atualizar Executáveis",
            command=self.iniciar_atualizacao_outros,
            bg="#FFD700",
            fg="black",
            font=("Segoe UI", 9, "bold"),
            state=tk.DISABLED,
        )
        self.btn_atualizar_outros.pack(side=tk.LEFT)

        # 5. Status e Ações
        frame_acoes = tk.Frame(self.coluna_esq, pady=4)
        frame_acoes.pack(fill="x")

        frame_status = tk.Frame(frame_acoes)
        frame_status.pack(fill="x", pady=(0, 8))

        tk.Label(
            frame_status,
            text="Vídeos Escolhidos / Baixados:",
            font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT)
        self.txt_progresso = tk.Entry(
            frame_status,
            width=12,
            font=("Segoe UI", 10, "bold"),
            justify="center",
            fg="#0000FF",
        )
        self.txt_progresso.pack(side=tk.LEFT, padx=8)
        self.txt_progresso.insert(0, "0 / 0")
        self.txt_progresso.config(state="readonly")

        frame_botoes = tk.Frame(frame_acoes)
        frame_botoes.pack(fill="x")

        self.btn_baixar_video = tk.Button(
            frame_botoes,
            text="BAIXAR SOMENTE O DO LINK",
            bg="#D32F2F",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            state=tk.DISABLED,
            command=lambda: self.iniciar_download(modo_playlist=False),
        )
        self.btn_baixar_video.pack(
            side=tk.LEFT, expand=True, fill="x", padx=(0, 2), ipady=4
        )

        self.btn_baixar_playlist = tk.Button(
            frame_botoes,
            text="BAIXAR ESCOLHIDOS DA PLAYLIST",
            bg="#7B1FA2",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            state=tk.DISABLED,
            command=lambda: self.iniciar_download(modo_playlist=True),
        )
        self.btn_baixar_playlist.pack(
            side=tk.LEFT, expand=True, fill="x", padx=(2, 2), ipady=4
        )

        self.btn_cancelar = tk.Button(
            frame_botoes,
            text="CANCELAR",
            bg="grey",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            state=tk.DISABLED,
            command=self.confirmar_cancelamento,
        )
        self.btn_cancelar.pack(side=tk.LEFT, padx=(2, 0), ipady=4, ipadx=8)

        # 6. Log estilo Prompt
        self.log = scrolledtext.ScrolledText(
            self.coluna_esq,
            height=10,
            bg="black",
            fg="#00FF00",
            insertbackground="white",
            font=("Consolas", 9),
        )
        self.log.pack(fill="both", expand=True, pady=(8, 0))

        # Coluna Direita (Lista de Vídeos)
        self.frame_lista_videos = tk.LabelFrame(
            self.coluna_dir,
            text=" Vídeos Encontrados na Playlist ",
            padx=8,
            pady=8,
        )
        self.frame_lista_videos.pack(fill="both", expand=True)

        self.var_selecionar_todos = tk.IntVar(value=1)
        self.cb_todos = tk.Checkbutton(
            self.frame_lista_videos,
            text="Selecionar Todos",
            variable=self.var_selecionar_todos,
            command=self.toggle_todos,
            state=tk.DISABLED,
            font=("Segoe UI", 9, "bold"),
        )
        self.cb_todos.pack(anchor="w", pady=(0, 4))

        # Canvas com Scrollbar
        self.canvas_lista = tk.Canvas(self.frame_lista_videos, bg="white")
        self.scrollbar_lista = tk.Scrollbar(
            self.frame_lista_videos,
            orient="vertical",
            command=self.canvas_lista.yview,
        )
        self.scrollable_frame = tk.Frame(self.canvas_lista, bg="white")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas_lista.configure(
                scrollregion=self.canvas_lista.bbox("all")
            ),
        )
        self.canvas_lista.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.canvas_lista.configure(yscrollcommand=self.scrollbar_lista.set)

        self.canvas_lista.pack(side=tk.LEFT, fill="both", expand=True)
        self.scrollbar_lista.pack(side=tk.RIGHT, fill="y")

        tk.Label(
            self.scrollable_frame,
            text="Cole um link e clique em 'Buscar Prévia' para carregar a lista.",
            bg="white",
            font=("Segoe UI", 10, "italic"),
            fg="gray",
        ).pack(anchor="w", pady=20, padx=10)

    # --- AÇÕES DA INTERFACE ---
    def estado_botoes_ocioso(self):
        self.entry_link.config(state=tk.NORMAL)
        self.entry_pasta.config(state=tk.NORMAL)
        self.rb_video.config(state=tk.NORMAL)
        self.rb_audio.config(state=tk.NORMAL)
        self.rb_ambos.config(state=tk.NORMAL)
        self.btn_colar.config(state=tk.NORMAL)
        self.btn_previa.config(state=tk.NORMAL, bg="#2196F3")
        self.btn_procurar.config(state=tk.NORMAL)
        self.btn_abrir_pasta.config(state=tk.NORMAL, bg="#4CAF50")
        self.btn_atualizar_outros.config(state=tk.NORMAL, bg="#FFD700")
        self.cb_todos.config(state=tk.NORMAL)
        for cb in self.checkbuttons_videos:
            cb.config(state=tk.NORMAL)

        self.btn_baixar_video.config(state=tk.NORMAL, bg="#D32F2F")
        self.btn_baixar_playlist.config(state=tk.NORMAL, bg="#7B1FA2")
        self.btn_cancelar.config(state=tk.DISABLED, bg="grey")

        if self.lbl_imagem.cget("text") == "Aguardando atualização...":
            self.lbl_imagem.config(text="Nenhuma prévia carregada.")

    def estado_botoes_baixando(self):
        self.btn_baixar_video.config(state=tk.DISABLED, bg="grey")
        self.btn_baixar_playlist.config(state=tk.DISABLED, bg="grey")
        self.btn_atualizar_outros.config(state=tk.DISABLED, bg="grey")
        self.btn_cancelar.config(state=tk.NORMAL, bg="#FF9800")
        self.cb_todos.config(state=tk.DISABLED)
        for cb in self.checkbuttons_videos:
            cb.config(state=tk.DISABLED)

    def colar_e_extrair(self):
        try:
            texto = self.root.clipboard_get().strip()
            self.entry_link.delete(0, tk.END)
            self.entry_link.insert(0, texto)
            self.iniciar_previa()
        except tk.TclError:
            messagebox.showwarning(
                "Aviso", "A área de transferência está vazia!"
            )

    def escolher_pasta(self):
        pasta = filedialog.askdirectory(
            title="Selecione a pasta de salvamento",
            initialdir=self.pasta_destino.get(),
        )
        if pasta:
            self.pasta_destino.set(os.path.normpath(pasta))
            self.salvar_config()

    def abrir_pasta(self):
        pasta = self.pasta_destino.get().strip()
        if not os.path.exists(pasta):
            os.makedirs(pasta, exist_ok=True)
        os.startfile(pasta)

    def escrever_log(self, texto):
        self.log.insert(tk.END, texto + "\n")
        self.log.see(tk.END)

    def atualizar_progresso(self, atual, total):
        self.txt_progresso.config(state=tk.NORMAL)
        self.txt_progresso.delete(0, tk.END)
        self.txt_progresso.insert(0, f"{atual} / {total}")
        self.txt_progresso.config(state="readonly")

    def toggle_todos(self):
        estado = self.var_selecionar_todos.get()
        for var in self.vars_videos:
            var.set(estado)

    # --- PRÉVIA E BUSCA ---
    def iniciar_previa(self):
        link = self.entry_link.get().strip()
        if not link:
            return
        self.lbl_titulo.config(text="Buscando informações do vídeo...")
        self.btn_previa.config(state=tk.DISABLED, bg="grey")
        threading.Thread(
            target=self.processar_previa, args=(link,), daemon=True
        ).start()

    def processar_previa(self, link):
        cmd_flat = [
            self.caminho_ytdlp,
            "--flat-playlist",
            "--dump-json",
            link,
        ]
        titulos = []
        try:
            proc = subprocess.Popen(
                cmd_flat,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding="utf-8",
                errors="replace",
            )
            out, _ = proc.communicate()
            if proc.returncode == 0 and out:
                for line in out.strip().split("\n"):
                    if line:
                        try:
                            d = json.loads(line)
                            titulos.append(d.get("title", "Sem título"))
                        except Exception:
                            pass
        except Exception:
            pass

        self.root.after(0, self.atualizar_lista_interface, titulos)

        cmd_previa = [
            self.caminho_ytdlp,
            "--dump-json",
            "--no-playlist",
            link,
        ]
        try:
            proc_p = subprocess.Popen(
                cmd_previa,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                encoding="utf-8",
                errors="replace",
            )
            out_p, _ = proc_p.communicate()
            if proc_p.returncode == 0 and out_p:
                dados = json.loads(out_p)
                titulo = dados.get("title", "Sem título")
                duracao = dados.get("duration_string", "Desconhecida")
                thumb = dados.get("thumbnail", "")
                self.root.after(
                    0, self.atualizar_textos_previa, titulo, duracao
                )
                if HAS_PIL and thumb:
                    self.baixar_imagem(thumb)
        except Exception:
            self.root.after(
                0, self.atualizar_textos_previa, "Erro ao obter prévia.", "-"
            )
        finally:
            self.root.after(
                0,
                lambda: self.btn_previa.config(
                    state=tk.NORMAL, bg="#2196F3"
                ),
            )

    def atualizar_lista_interface(self, titulos):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        self.vars_videos.clear()
        self.checkbuttons_videos.clear()

        if not titulos:
            tk.Label(
                self.scrollable_frame,
                text="Vídeo único detectado ou nenhum item na lista.",
                bg="white",
                font=("Segoe UI", 9),
            ).pack(anchor="w", pady=10, padx=10)
            self.atualizar_progresso("0", "1")
            return

        self.var_selecionar_todos.set(1)
        for i, t in enumerate(titulos):
            var = tk.IntVar(value=1)
            self.vars_videos.append(var)
            cb = tk.Checkbutton(
                self.scrollable_frame,
                text=f"{i+1}. {t}",
                variable=var,
                bg="white",
                font=("Segoe UI", 9),
                anchor="w",
                justify="left",
            )
            cb.pack(anchor="w", fill="x", pady=1, padx=4)
            self.checkbuttons_videos.append(cb)

        self.atualizar_progresso("0", str(len(titulos)))

    def atualizar_textos_previa(self, titulo, duracao):
        self.lbl_titulo.config(text=f"Título: {titulo}")
        self.lbl_duracao.config(text=f"Duração: {duracao}")

    def baixar_imagem(self, url):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            data = urllib.request.urlopen(req).read()
            img = Image.open(BytesIO(data))
            img.thumbnail((220, 130))
            foto = ImageTk.PhotoImage(img)
            self.root.after(0, self.mostrar_imagem, foto)
        except Exception:
            pass

    def mostrar_imagem(self, foto):
        self.lbl_imagem.config(image=foto, width=220, height=130, text="")
        self.lbl_imagem.image = foto

    # --- PROCESSAMENTO DE DOWNLOAD ---
    def iniciar_download(self, modo_playlist=False):
        link = self.entry_link.get().strip()
        saida = self.pasta_destino.get().strip()
        formato = self.formato_escolhido.get()

        if not link:
            messagebox.showwarning("Erro", "Insira um link do YouTube.")
            return

        indices = []
        if modo_playlist:
            indices = [
                str(i + 1)
                for i, v in enumerate(self.vars_videos)
                if v.get() == 1
            ]
            if not indices and self.vars_videos:
                messagebox.showwarning(
                    "Aviso", "Nenhum vídeo da lista selecionado!"
                )
                return

        self.estado_botoes_baixando()
        self.download_cancelado = False

        threading.Thread(
            target=self.processar_download,
            args=(link, saida, formato, modo_playlist, indices),
            daemon=True,
        ).start()

    def processar_download(self, link, saida, formato, modo_playlist, indices):
        if modo_playlist and indices:
            template = os.path.join(
                saida,
                "%(playlist_title|Playlist)s",
                "%(playlist_index)02d - %(title)s.%(ext)s",
            )
            flags_lista = [
                "--yes-playlist",
                "--playlist-items",
                ",".join(indices),
            ]
        else:
            template = os.path.join(saida, "%(title)s.%(ext)s")
            flags_lista = ["--no-playlist"]

        cmd_base = [self.caminho_ytdlp] + flags_lista

        formatos_executar = []
        if formato in (1, 3):  # Vídeo MP4 com áudio AAC
            formatos_executar.append(
                [
                    "-f",
                    "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
                    "--merge-output-format",
                    "mp4",
                ]
            )
        if formato in (2, 3):  # Áudio M4A/AAC puro
            formatos_executar.append(
                [
                    "-f",
                    "ba[ext=m4a]/bestaudio",
                    "-x",
                    "--audio-format",
                    "m4a",
                    "--audio-quality",
                    "0",
                ]
            )

        for param_fmt in formatos_executar:
            if self.download_cancelado:
                break

            comando = cmd_base + param_fmt + ["-o", template, link]

            try:
                self.processo_atual = subprocess.Popen(
                    comando,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    encoding="utf-8",
                    errors="replace",
                )

                for linha in self.processo_atual.stdout:
                    line_str = linha.strip()
                    self.root.after(0, self.escrever_log, line_str)

                    match = re.search(
                        r"downloading (?:video|item) (\d+) of (\d+)",
                        line_str,
                        re.IGNORECASE,
                    )
                    if match:
                        self.root.after(
                            0,
                            self.atualizar_progresso,
                            match.group(1),
                            match.group(2),
                        )

                self.processo_atual.wait()
            except Exception as e:
                self.root.after(0, self.escrever_log, f"Erro: {e}")

        self.processo_atual = None
        self.root.after(0, self.estado_botoes_ocioso)

    def confirmar_cancelamento(self):
        if messagebox.askyesno("Cancelar", "Deseja cancelar o download?"):
            self.download_cancelado = True
            if self.processo_atual:
                try:
                    self.processo_atual.terminate()
                except Exception:
                    pass


if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderYouTubePro(root)
    root.mainloop()