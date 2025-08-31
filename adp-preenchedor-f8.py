# -*- coding: utf-8 -*-
"""
Preenchedor ADP (GUI) v6.2 — F8 EXCLUSIVO (sem repique)
Autor: Anderson + ChatGPT

Mudanças v6.2 (anti-repique):
- F8 EXCLUSIVO: só envia com F8 “puro” (sem Shift/Ctrl/Alt).
- Removido Shift+F8 (reenviar) para evitar dupla rota.
- Debounce e trava de reentrada no on_enviar (ignora disparo duplo em ~300ms).
- Quando Hotkey Global está ativa, desativamos o binding local de F8 para evitar duplicidade.

Fluxo:
- F8 → envia valor e, se configurado, TAB.
- F6 → pular campo.
- Ctrl+K → alterna ignorar [SKIP] na sessão.
- F9 → voltar.

Dependências:
  pip install customtkinter pandas pyautogui openpyxl pynput
  * Hotkeys globais exigem sessão Xorg (echo $XDG_SESSION_TYPE -> x11/xorg).
"""

import time
import pandas as pd
import pyautogui as pg
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path

# Hotkeys globais sem root (Xorg)
try:
    from pynput import keyboard as pk  # type: ignore
    HAS_PYNPUT = True
except Exception:
    HAS_PYNPUT = False

pg.PAUSE = 0.0
pg.FAILSAFE = True

APP_TITLE = "Preenchedor ADP (GUI) v6.2 — F8 exclusivo | F6 pula | Ctrl+K ignora"

SKIP_PREFIXES = ("#", "[skip]", "skip_")
SKIP_SUFFIXES = ("_skip",)

def to_str(v):
    if v is None:
        return ""
    s = str(v)
    return "" if s.lower() == "nan" else s

def is_template_skip(colname: str) -> bool:
    n = colname.strip().lower()
    for p in SKIP_PREFIXES:
        if n.startswith(p):
            return True
    for s in SKIP_SUFFIXES:
        if n.endswith(s):
            return True
    return False

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x640")
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Estado
        self.df = None
        self.registro = {}
        self.campos = []   # lista de dicts: {"nome": str, "skip": bool}
        self.i = 0

        # Anti-repique
        self._debounce_secs = 0.30
        self._last_enviar_at = 0.0
        self._sending = False

        # Listener global
        self.hk_listener = None
        self.global_on = False
        self._local_f8_bound = False  # controla bind local do F8

        # Top — seleção
        self.frame_top = ctk.CTkFrame(self); self.frame_top.pack(fill="x", padx=12, pady=(12,6))
        self.entry_arquivo = ctk.CTkEntry(self.frame_top, placeholder_text="Arquivo Excel (.xlsx)")
        self.entry_arquivo.pack(side="left", fill="x", expand=True, padx=(8,6), pady=8)
        self.btn_arquivo = ctk.CTkButton(self.frame_top, text="Escolher...", command=self.escolher_arquivo, width=120)
        self.btn_arquivo.pack(side="left", padx=6, pady=8)
        self.cmb_sheet = ctk.CTkComboBox(self.frame_top, values=[], width=240); self.cmb_sheet.set("Template_Inputs_TabOrder")
        self.cmb_sheet.pack(side="left", padx=6, pady=8)
        self.entry_linha = ctk.CTkEntry(self.frame_top, width=80, placeholder_text="Linha (1..)"); self.entry_linha.insert(0, "1")
        self.entry_linha.pack(side="left", padx=6, pady=8)
        self.btn_carregar = ctk.CTkButton(self.frame_top, text="Carregar", command=self.carregar_dados, width=120)
        self.btn_carregar.pack(side="left", padx=6, pady=8)

        # Mid — preview + ordem
        self.frame_mid = ctk.CTkFrame(self); self.frame_mid.pack(fill="both", expand=True, padx=12, pady=6)
        self.txt_preview = ctk.CTkTextbox(self.frame_mid, width=660, height=420)
        self.txt_preview.pack(side="left", fill="both", expand=True, padx=(8,6), pady=8)
        self.frame_ordem = ctk.CTkFrame(self.frame_mid); self.frame_ordem.pack(side="left", fill="y", padx=(6,8), pady=8)
        self.lbl_ordem = ctk.CTkLabel(self.frame_ordem, text="Ordem de campos (marcados com [SKIP] serão ignorados):")
        self.lbl_ordem.pack(pady=(8,4))
        self.listbox = ctk.CTkTextbox(self.frame_ordem, width=360, height=380); self.listbox.pack(padx=6, pady=4)

        # Bottom — controles
        self.frame_bot = ctk.CTkFrame(self); self.frame_bot.pack(fill="x", padx=12, pady=(6,12))
        self.chk_tab = ctk.CTkCheckBox(self.frame_bot, text="Enviar TAB após digitar (opcional)", onvalue=True, offvalue=False)
        self.chk_tab.deselect()  # por padrão, NÃO envia TAB
        self.chk_tab.pack(side="left", padx=8, pady=8)

        self.btn_iniciar = ctk.CTkButton(self.frame_bot, text="Iniciar", command=self.iniciar, fg_color="#198754", hover_color="#157347")
        self.btn_iniciar.pack(side="left", padx=8, pady=8)

        self.btn_hotkey = ctk.CTkButton(self.frame_bot, text="Ativar HOTKEY Global (F8/F6)", command=self.toggle_global, fg_color="#0d6efd", hover_color="#0b5ed7")
        self.btn_hotkey.pack(side="left", padx=8, pady=8)

        self.btn_pular = ctk.CTkButton(self.frame_bot, text="Pular (F6)", command=lambda: self.on_pular(marcar=False))
        self.btn_pular.pack(side="left", padx=8, pady=8)

        self.btn_toggle_skip = ctk.CTkButton(self.frame_bot, text="Ignorar/Restaurar (Ctrl+K)", command=self.toggle_ignore)
        self.btn_toggle_skip.pack(side="left", padx=8, pady=8)

        self.btn_voltar = ctk.CTkButton(self.frame_bot, text="Voltar (F9)", command=self.on_voltar)
        self.btn_voltar.pack(side="left", padx=8, pady=8)

        self.lbl_status = ctk.CTkLabel(self.frame_bot, text="Aguardando arquivo...")
        self.lbl_status.pack(side="left", padx=12, pady=8)

        # Bindings locais (backup dentro da janela) — F8 EXCLUSIVO
        self._bind_local_keys()

        self.update_preview("Selecione o Excel. Dica de template: prefixe a COLUNA com # ou [SKIP] para ignorar (ex.: #nome_social).")

    # --- Helpers de binding local ---
    def _bind_local_keys(self):
        # F8 exclusivo: vamos checar modificadores dentro do handler
        self.bind("<F8>", self._on_f8_local)
        self._local_f8_bound = True

        self.bind("<F6>", lambda e: self.on_pular(marcar=False))
        self.bind("<Control-k>", lambda e: self.toggle_ignore())
        self.bind("<F9>", lambda e: self.on_voltar())

    def _unbind_local_f8(self):
        if self._local_f8_bound:
            try:
                self.unbind("<F8>")
            except Exception:
                pass
            self._local_f8_bound = False

    # --- Checar modificadores (Tk state bitmask) ---
    def _has_modifiers(self, event) -> bool:
        st = getattr(event, "state", 0)
        # Shift (0x0001), Control (0x0004), Alt/Meta (0x0008)
        if st & 0x0001:  # Shift
            return True
        if st & 0x0004:  # Control
            return True
        if st & 0x0008:  # Alt (Mod1)
            return True
        return False

    def _on_f8_local(self, event):
        # Só executa se NÃO houver modificadores — F8 EXCLUSIVO
        if self._has_modifiers(event):
            return
        self.on_enviar(avancar=True)

    # --- Hotkey global ---
    def toggle_global(self):
        if not HAS_PYNPUT:
            messagebox.showerror("Hotkey Global", "Instale 'pynput' e use sessão Xorg (echo $XDG_SESSION_TYPE deve ser x11).")
            return
        if self.df is None:
            messagebox.showwarning("Iniciar", "Carregue o Excel e clique 'Iniciar' antes de ativar a hotkey.")
            return
        if not self.global_on:
            try:
                # Desliga F8 local para evitar duplicidade
                self._unbind_local_f8()

                mapping = {
                    "<f8>":         lambda: self.after(0, lambda: self.on_enviar(avancar=True)),
                    # Sem Shift+F8 para evitar repique
                    "<f6>":         lambda: self.after(0, lambda: self.on_pular(marcar=False)),
                    "<ctrl>+k":     lambda: self.after(0, self.toggle_ignore),
                    "<f9>":         lambda: self.after(0, self.on_voltar),
                }
                self.hk_listener = pk.GlobalHotKeys(mapping); self.hk_listener.start()
                self.global_on = True
                self.btn_hotkey.configure(text="Desativar HOTKEY Global", fg_color="#6c757d", hover_color="#5c636a")
                self.lbl_status.configure(text="Ativo: F8 envia (exclusivo), F6 pula, Ctrl+K ignora, F9 volta.")
            except Exception as e:
                messagebox.showerror("Hotkey Global", f"Falha ao ativar (pynput):\n{e}\nConfirme Xorg.")
        else:
            try:
                if self.hk_listener: self.hk_listener.stop()
            except Exception:
                pass
            self.hk_listener = None
            self.global_on = False
            # Reativa F8 local
            self.bind("<F8>", self._on_f8_local)
            self._local_f8_bound = True

            self.btn_hotkey.configure(text="Ativar HOTKEY Global (F8/F6)", fg_color="#0d6efd", hover_color="#0b5ed7")
            self.lbl_status.configure(text="Hotkey global desativada. F8 local reativado (exclusivo).")

    # --- Fluxo ---
    def iniciar(self):
        if self.df is None:
            messagebox.showwarning("Carregar", "Carregue o Excel primeiro.")
            return
        self.i = 0
        # posiciona no primeiro não-skip
        self._pular_skips_automaticamente(sentido=+1)
        self.lbl_status.configure(text="Iniciado. F8 exclusivo para enviar; F6 para pular; Ctrl+K ignora.")
        self.update_preview()

    def on_enviar(self, avancar: bool):
        # Anti-repique: trava de reentrada + debounce
        if self._sending:
            return
        now = time.monotonic()
        if (now - self._last_enviar_at) < self._debounce_secs:
            return
        self._last_enviar_at = now
        self._sending = True
        try:
            if self.df is None:
                return
            if self.i >= len(self.campos):
                self.lbl_status.configure(text="Concluído.")
                return

            campo = self.campos[self.i]
            if campo["skip"]:
                # apenas avance para próximo não-skip
                self._pular_skips_automaticamente(sentido=+1)
                self.update_preview("Campo ignorado pelo template. Avançando...")
                return

            col = campo["nome"]
            val = to_str(self.registro.get(col, ""))

            # Digita (sem trocar foco; você mantém o ADP focado)
            if len(val) > 0:
                # write == typewrite
                pg.write(val, interval=0.02)

            if bool(self.chk_tab.get()):
                pg.press("tab")

            if avancar:
                self.i += 1
                self._pular_skips_automaticamente(sentido=+1)

            self.update_preview()
        finally:
            # pequena folga para garantir estabilidade entre toques
            time.sleep(0.02)
            self._sending = False

    def on_pular(self, marcar: bool = False):
        """Pula este campo sem digitar. Se marcar=True, define skip=True (sessão)."""
        if self.df is None: return
        if self.i >= len(self.campos): return
        if marcar:
            self.campos[self.i]["skip"] = True
        self.i += 1
        self._pular_skips_automaticamente(sentido=+1)
        self.update_preview("Campo pulado.")

    def toggle_ignore(self):
        """Alterna o status 'skip' do campo atual (sessão)."""
        if self.df is None: return
        if self.i >= len(self.campos): return
        self.campos[self.i]["skip"] = not self.campos[self.i]["skip"]
        estado = "IGNORADO" if self.campos[self.i]["skip"] else "ATIVO"
        self.update_preview(f"Campo marcado como {estado}.")

    def on_voltar(self):
        if self.df is None: return
        if self.i > 0:
            self.i -= 1
            self._pular_skips_automaticamente(sentido=-1)
        self.update_preview("Voltou um campo.")

    # --- utilitários ---
    def _pular_skips_automaticamente(self, sentido: int):
        """Avança (ou retrocede) até um campo não-skip. sentido=+1 para frente, -1 para trás."""
        n = len(self.campos)
        while 0 <= self.i < n and self.campos[self.i]["skip"]:
            self.i += sentido

    def escolher_arquivo(self):
        p = filedialog.askopenfilename(title="Escolha o Excel de admissão", filetypes=[("Excel", "*.xlsx *.xls")])
        if not p: return
        self.entry_arquivo.delete(0, "end"); self.entry_arquivo.insert(0, p)
        try:
            xls = pd.ExcelFile(p); self.cmb_sheet.configure(values=xls.sheet_names)
            if "Template_Inputs_TabOrder" in xls.sheet_names: self.cmb_sheet.set("Template_Inputs_TabOrder")
            elif "Template_Inputs_Form" in xls.sheet_names: self.cmb_sheet.set("Template_Inputs_Form")
            else: self.cmb_sheet.set(xls.sheet_names[0])
        except Exception as e:
            messagebox.showerror("Erro", f"Não consegui ler as abas do Excel:\n{e}")

    def carregar_dados(self):
        path = self.entry_arquivo.get().strip()
        if not path:
            messagebox.showwarning("Arquivo", "Informe o arquivo do Excel.")
            return
        sheet = self.cmb_sheet.get().strip()
        if not sheet:
            messagebox.showwarning("Sheet", "Selecione a aba do Excel.")
            return
        try:
            df = pd.read_excel(path, sheet_name=sheet, dtype=str)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao ler o Excel/aba:\n{e}")
            return

        if df.empty or len(df.columns) == 0:
            messagebox.showerror("Erro", "A aba selecionada está vazia.")
            return

        try:
            row_1b = int(self.entry_linha.get().strip())
            if row_1b <= 0: raise ValueError
        except Exception:
            messagebox.showerror("Linha", "Informe a linha (1, 2, 3, ...)")
            return
        row_idx = row_1b - 1
        if row_idx >= len(df):
            messagebox.showerror("Linha", f"Índice de linha fora do intervalo. Linhas disponíveis: 1..{len(df)}")
            return

        self.df = df
        self.registro = df.iloc[row_idx].to_dict()

        # montar campos com flags de skip
        self.campos = []
        for col in list(df.columns):
            self.campos.append({"nome": col, "skip": is_template_skip(col)})

        self.i = 0
        self._pular_skips_automaticamente(sentido=+1)

        # Render lista
        self._render_lista()
        self.lbl_status.configure(text=f"Planilha: {Path(path).name} | Aba: {sheet} | Linha: {row_1b}")
        self.update_preview("Arquivo e linha carregados. Clique Iniciar.")

    def _render_lista(self):
        self.listbox.configure(state="normal"); self.listbox.delete("1.0", "end")
        for idx, c in enumerate(self.campos, start=1):
            nome = c["nome"]
            tag = " [SKIP]" if c["skip"] else ""
            self.listbox.insert("end", f"{idx:03d}  {nome}{tag}\n")
        self.listbox.configure(state="disabled")

    def update_preview(self, msg=None):
        self.txt_preview.configure(state="normal"); self.txt_preview.delete("1.0", "end")
        if msg: self.txt_preview.insert("end", msg + "\n\n")
        if self.df is not None:
            if 0 <= self.i < len(self.campos):
                c = self.campos[self.i]
                val = to_str(self.registro.get(c["nome"], ""))
                skip_txt = " [SKIP]" if c["skip"] else ""
                self.txt_preview.insert("end", f"Campo atual ({self.i+1}/{len(self.campos)}): {c['nome']}{skip_txt}\nValor: {val}\n")
            else:
                self.txt_preview.insert("end", "Sem próximos campos.\n")
        else:
            self.txt_preview.insert("end", "Selecione um arquivo para começar.\n")
        self.txt_preview.configure(state="disabled")
        # re-render list (para refletir toggles)
        self._render_lista()

if __name__ == "__main__":
    app = App()
    app.mainloop()
