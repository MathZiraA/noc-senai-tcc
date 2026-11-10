"""Serve uma pasta por HTTP com suporte a Range (leitura em pedaços), para a iDRAC montar uma ISO pela rede.

O http.server padrão do Python ignora o cabeçalho Range e a iDRAC (Remote File Share por HTTP) recusa a imagem
com o erro RAC0720. Somente leitura; para quando a janela for fechada (Ctrl+C).
Uso: python bancada\\servir_iso.py <pasta> [ip] [porta]
"""
import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PASTA = sys.argv[1] if len(sys.argv) > 1 else "."
IP = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
PORTA = int(sys.argv[3]) if len(sys.argv) > 3 else 8080


class ComRange(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        caminho = self.translate_path(self.path)
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        if not m or not os.path.isfile(caminho):
            return super().send_head()
        tamanho = os.path.getsize(caminho)
        ini = int(m.group(1)) if m.group(1) else max(0, tamanho - int(m.group(2)))
        fim = int(m.group(2)) if m.group(1) and m.group(2) else tamanho - 1
        fim = min(fim, tamanho - 1)
        if ini > fim:
            self.send_error(416, "Range fora do arquivo")
            return None
        f = open(caminho, "rb")
        f.seek(ini)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(caminho))
        self.send_header("Content-Range", f"bytes {ini}-{fim}/{tamanho}")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.end_headers()
        self._restante = fim - ini + 1
        return f

    def copyfile(self, origem, destino):
        restante = getattr(self, "_restante", None)
        if restante is None:
            return super().copyfile(origem, destino)
        while restante > 0:
            bloco = origem.read(min(65536, restante))
            if not bloco:
                break
            destino.write(bloco)
            restante -= len(bloco)


if __name__ == "__main__":
    servidor = ThreadingHTTPServer((IP, PORTA), partial(ComRange, directory=PASTA))
    print(f"Servindo {os.path.abspath(PASTA)} em http://{IP}:{PORTA}/ (Range ativo). Ctrl+C para parar.")
    servidor.serve_forever()
