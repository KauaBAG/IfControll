"""
tab_config.py — Sub-aba 5: Configuração da API.
"""

import threading

import tkinter as tk

from utils.theme_manager import C
import core.credencials as _cred

from core.api import _cron_get, _cron_url, _cron_key
from ._helpers import lbl, ent, btn, txtbox, write


class ConfigMixin:
    """
    Mixin com toda a lógica da sub-aba Configuração.
    Deve ser misturado em TabCronologia.
    """

    def _build_config(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" ⚙ Configuração ")

        b = tk.Frame(f, bg=C["bg"])
        b.pack(fill="both", expand=True, padx=20, pady=16)

        lbl(b, "CONFIGURAÇÃO DA API PHP", 11, True, C["accent"]).pack(anchor="w", pady=(0, 10))

        lbl(b, "URL da API:", 9, col=C["text_mid"]).pack(anchor="w", pady=(4, 2))
        self.e_api_url = ent(b)
        self.e_api_url.pack(fill="x", ipady=5)
        self.e_api_url.insert(0, _cron_url())

        lbl(b, "Token:", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.e_api_key = ent(b, show="*")
        self.e_api_key.pack(fill="x", ipady=5)
        self.e_api_key.insert(0, _cron_key())

        fr, self.res_cfg = txtbox(b, 6)
        fr.pack(fill="x", pady=(12, 0))

        def salvar():
            _cred.CRON_API_URL = self.e_api_url.get().strip().rstrip("/")
            _cred.CRON_API_KEY = self.e_api_key.get().strip()
            write(self.res_cfg,
                  f"✔ Salvo!\nURL: {_cred.CRON_API_URL}", C["success"])

        def testar():
            write(self.res_cfg, "⏳ Testando...", C["accent"])
            _cred.CRON_API_URL = self.e_api_url.get().strip().rstrip("/")
            _cred.CRON_API_KEY = self.e_api_key.get().strip()

            def task():
                resp = _cron_get("ping")
                if resp.get("status"):
                    d   = resp.get("data") or {}
                    msg = (f"✔ OK!\n{d.get('mensagem', '—')}\n"
                           f"{d.get('timestamp', '—')}\n"
                           f"Versão API: {d.get('versao', '—')}")
                    self.after(0, lambda: write(self.res_cfg, msg, C["success"]))
                else:
                    err = f"✖ {resp.get('error', 'Falha na conexão')}"
                    self.after(0, lambda: write(self.res_cfg, err, C["danger"]))

            threading.Thread(target=task, daemon=True).start()

        row = tk.Frame(b, bg=C["bg"])
        row.pack(pady=12)
        btn(row, "💾 SALVAR", salvar, C["accent"]).pack(side="left", padx=6)
        btn(row, "🔌 TESTAR", testar, C["green"]).pack(side="left", padx=6)
