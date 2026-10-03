"""Gera o visual do mapa da topologia: fundo (1400x790) e ícones arredondados em tons pastel,
cada um com uma versão vermelha usada quando o equipamento tem problema.
Roda no notebook (precisa de Pillow e das fontes Segoe UI); grava os PNGs em noc/mapa/."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SAIDA = Path(__file__).parent / "mapa"
FONTES = Path("C:/Windows/Fonts")
X = 4  # desenha em 4x e reduz: bordas suaves

LARGURA, ALTURA = 1400, 790
FUNDO, CARTAO, BORDA = "#F6F8FB", "#FFFFFF", "#E2E8F0"
TEXTO, SUAVE = "#1F2933", "#7B8794"
MATRIZ = ("#EAF2FF", "#C9DCFB", "#3B6FB6")
FILIAL = ("#E9F8EF", "#C3E8D1", "#2E8B57")
VERDE, VERMELHO, LARANJA, AMARELO = "#3FB58A", "#E5484D", "#F2A33A", "#E6C229"
ICONES = {"roteador": "#5B8DEF", "switch": "#8B7CF0", "antena": "#F2A33A", "servidor": "#3FB58A", "pcs": "#8A9BB0"}
ALERTA = "#E5484D"


def fonte(nome, tamanho):
    return ImageFont.truetype(str(FONTES / nome), tamanho * X)


def caixa(d, x0, y0, x1, y1, raio, preenchimento, borda=None, largura=1):
    d.rounded_rectangle([x0 * X, y0 * X, x1 * X, y1 * X], raio * X, fill=preenchimento,
                        outline=borda, width=largura * X)


def sombra(img, x0, y0, x1, y1, raio, deslocamento=4, desfoque=10, alfa=40):
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(camada).rounded_rectangle(
        [x0 * X, (y0 + deslocamento) * X, x1 * X, (y1 + deslocamento) * X], raio * X, fill=(31, 41, 51, alfa))
    img.alpha_composite(camada.filter(ImageFilter.GaussianBlur(desfoque * X / 2)))


def texto(d, x, y, conteudo, f, cor, ancora="la"):
    d.text((x * X, y * X), conteudo, font=f, fill=cor, anchor=ancora)


def fundo():
    img = Image.new("RGBA", (LARGURA * X, ALTURA * X), FUNDO)
    d = ImageDraw.Draw(img)
    # título
    sombra(img, 30, 20, LARGURA - 30, 86, 18)
    caixa(d, 30, 20, LARGURA - 30, 86, 18, CARTAO, BORDA)
    texto(d, 56, 53, "Rede SENAI · Matriz ↔ Filial", fonte("seguisb.ttf", 26), TEXTO, "lm")
    texto(d, LARGURA - 56, 53, "redundância Fibra + Rádio · tempo real", fonte("segoeui.ttf", 17), SUAVE, "rm")
    # zonas
    for (x0, x1), (cor, borda, tinta), nome, rede in (
            ((30, 520), MATRIZ, "MATRIZ", "192.168.10.0/24"), ((880, 1370), FILIAL, "FILIAL", "192.168.20.0/24")):
        caixa(d, x0, 110, x1, 660, 28, cor, borda, 2)
        texto(d, x0 + 26, 140, nome, fonte("segoeuib.ttf", 20), tinta, "lm")
        texto(d, x0 + 26 + d.textlength(nome, font=fonte("segoeuib.ttf", 20)) / X + 12, 141, rede,
              fonte("segoeui.ttf", 15), tinta, "lm")
    texto(d, 700, 140, "ENLACES WAN", fonte("segoeuib.ttf", 15), SUAVE, "mm")
    texto(d, 700, 300, "fibra óptica · principal", fonte("segoeui.ttf", 14), SUAVE, "mm")
    texto(d, 700, 600, "rádio P2P · backup", fonte("segoeui.ttf", 14), SUAVE, "mm")
    # legenda
    sombra(img, 30, 680, LARGURA - 30, 768, 18)
    caixa(d, 30, 680, LARGURA - 30, 768, 18, CARTAO, BORDA)
    texto(d, 56, 724, "Legenda", fonte("seguisb.ttf", 16), TEXTO, "lm")
    itens = [(VERDE, "normal"), (VERMELHO, "caído"), (LARANJA, "perda ou instável"), (AMARELO, "previsão de piora")]
    x = 170
    f = fonte("segoeui.ttf", 15)
    for cor, nome in itens:
        d.line([x * X, 724 * X, (x + 36) * X, 724 * X], fill=cor, width=6 * X)
        texto(d, x + 46, 724, nome, f, TEXTO, "lm")
        x += 46 + d.textlength(nome, font=f) / X + 40
    d.ellipse([x * X, 714 * X, (x + 20) * X, 734 * X], fill=ALERTA)
    texto(d, x + 30, 724, "ícone vermelho = equipamento com problema", f, TEXTO, "lm")
    return img.resize((LARGURA, ALTURA), Image.LANCZOS)


def seta(d, x0, y0, x1, y1, cor, w):
    """Linha de (x0,y0) a (x1,y1) com ponta em (x1,y1), coordenadas já em 4x."""
    import math
    d.line([x0, y0, x1, y1], fill=cor, width=w)
    ang = math.atan2(y1 - y0, x1 - x0)
    p = 4.2 * w
    pontos = [(x1 + math.cos(ang) * p * 0.4, y1 + math.sin(ang) * p * 0.4),
              (x1 - math.cos(ang - 0.6) * p, y1 - math.sin(ang - 0.6) * p),
              (x1 - math.cos(ang + 0.6) * p, y1 - math.sin(ang + 0.6) * p)]
    d.polygon(pontos, fill=cor)


def icone(tipo, cor):
    T = 96
    img = Image.new("RGBA", (T * X, T * X), (0, 0, 0, 0))
    sombra(img, 10, 8, 86, 84, 24, deslocamento=4, desfoque=6, alfa=55)
    d = ImageDraw.Draw(img)
    caixa(d, 10, 8, 86, 84, 24, cor)
    branco, w = "#FFFFFF", 5 * X
    c = 48 * X  # centro horizontal
    m = 46 * X  # centro vertical
    if tipo == "roteador":
        d.ellipse([c - 24 * X, m - 24 * X, c + 24 * X, m + 24 * X], outline=branco, width=w)
        seta(d, c, m - 8 * X, c, m - 20 * X, branco, 4 * X)
        seta(d, c, m + 8 * X, c, m + 20 * X, branco, 4 * X)
        seta(d, c - 20 * X, m, c - 8 * X, m, branco, 4 * X)
        seta(d, c + 20 * X, m, c + 8 * X, m, branco, 4 * X)
    elif tipo == "switch":
        seta(d, c - 22 * X, m - 9 * X, c + 20 * X, m - 9 * X, branco, w)
        seta(d, c + 22 * X, m + 9 * X, c - 20 * X, m + 9 * X, branco, w)
    elif tipo == "antena":
        d.line([c, m - 8 * X, c, m + 24 * X], fill=branco, width=w)
        d.polygon([(c - 12 * X, m + 26 * X), (c + 12 * X, m + 26 * X), (c, m + 12 * X)], fill=branco)
        d.ellipse([c - 6 * X, m - 14 * X, c + 6 * X, m - 2 * X], fill=branco)
        for r in (14, 24):
            d.arc([c - r * X, m - 8 * X - r * X, c + r * X, m - 8 * X + r * X], 200, 250, fill=branco, width=4 * X)
            d.arc([c - r * X, m - 8 * X - r * X, c + r * X, m - 8 * X + r * X], 290, 340, fill=branco, width=4 * X)
    elif tipo == "servidor":
        for i in range(3):
            y = m - 22 * X + i * 16 * X
            d.rounded_rectangle([c - 22 * X, y, c + 22 * X, y + 12 * X], 4 * X, outline=branco, width=4 * X)
            d.ellipse([c + 11 * X, y + 4 * X, c + 15 * X, y + 8 * X], fill=branco)
    elif tipo == "pcs":
        d.rounded_rectangle([c - 24 * X, m - 20 * X, c + 24 * X, m + 10 * X], 5 * X, outline=branco, width=w)
        d.line([c, m + 10 * X, c, m + 18 * X], fill=branco, width=w)
        d.rounded_rectangle([c - 14 * X, m + 17 * X, c + 14 * X, m + 22 * X], 2 * X, fill=branco)
    return img.resize((T, T), Image.LANCZOS)


if __name__ == "__main__":
    SAIDA.mkdir(exist_ok=True)
    fundo().save(SAIDA / "NOC_fundo_topologia.png")
    for tipo, cor in ICONES.items():
        icone(tipo, cor).save(SAIDA / f"NOC_{tipo}.png")
        icone(tipo, ALERTA).save(SAIDA / f"NOC_{tipo}_alerta.png")
    print("imagens geradas em", SAIDA)
