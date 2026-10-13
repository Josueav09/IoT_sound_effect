"""Genera los sonidos de prueba (WAV) en la carpeta sonidos/.

Solo usa la biblioteca estandar. Ejecutar:  py generar_sonidos_prueba.py
Los archivos existentes con el mismo nombre se sobrescriben.
"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100
CARPETA = Path(__file__).resolve().parent / "sonidos"
random.seed(7)


def onda(freq, t, forma="seno"):
    fase = (freq * t) % 1.0
    if forma == "cuadrada":
        return 1.0 if fase < 0.5 else -1.0
    if forma == "sierra":
        return 2.0 * fase - 1.0
    if forma == "triangulo":
        return 4.0 * abs(fase - 0.5) - 1.0
    return math.sin(2 * math.pi * fase)


def nota(freq, dur, forma="seno", vol=0.6, ataque=0.005, caida=None):
    """Una nota con envolvente. freq puede ser una funcion f(t) para barridos."""
    n = int(RATE * dur)
    caida = dur * 0.6 if caida is None else caida
    out, fase = [], 0.0
    for i in range(n):
        t = i / RATE
        f = freq(t) if callable(freq) else freq
        fase += f / RATE
        env = min(1.0, t / ataque) if ataque else 1.0
        if t > dur - caida:
            env *= max(0.0, (dur - t) / caida)
        out.append(vol * env * onda(1.0, fase % 1.0, forma))
    return out


def ruido(dur, vol=0.5, caida_exp=8.0, suavizado=0.0):
    out, prev = [], 0.0
    for i in range(int(RATE * dur)):
        t = i / RATE
        x = random.uniform(-1, 1)
        prev = prev * suavizado + x * (1 - suavizado)
        out.append(vol * prev * math.exp(-caida_exp * t))
    return out


def silencio(dur):
    return [0.0] * int(RATE * dur)


def mezclar(*pistas):
    largo = max(len(p) for p in pistas)
    return [sum(p[i] for p in pistas if i < len(p)) for i in range(largo)]


def secuencia(*partes):
    out = []
    for p in partes:
        out.extend(p)
    return out


def guardar(nombre, muestras):
    pico = max(1e-9, max(abs(m) for m in muestras))
    escala = 0.9 / pico  # todos al mismo volumen maximo
    datos = b"".join(struct.pack("<h", int(m * escala * 32767)) for m in muestras)
    with wave.open(str(CARPETA / f"{nombre}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(datos)
    print(f"  {nombre}.wav  ({len(muestras) / RATE:.2f} s)")


DO, MI, SOL = 523.25, 659.25, 783.99

SONIDOS = {
    # 1: moneda
    "1": lambda: secuencia(nota(987.77, 0.08, "cuadrada", 0.35, caida=0.01),
                           nota(1318.5, 0.35, "cuadrada", 0.35)),
    # 2: laser (barrido hacia abajo)
    "2": lambda: nota(lambda t: 1600 * math.exp(-6 * t) + 150, 0.45, "sierra", 0.4),
    # 3: salto (barrido hacia arriba)
    "3": lambda: nota(lambda t: 300 + 1400 * t, 0.4, "cuadrada", 0.3),
    # 4: power-up (arpegio)
    "4": lambda: secuencia(*[nota(f, 0.09, "triangulo", 0.6, caida=0.02)
                             for f in (DO, MI, SOL, DO * 2, MI * 2, SOL * 2)]),
    # 5: error (zumbido grave)
    "5": lambda: secuencia(nota(150, 0.25, "cuadrada", 0.35, caida=0.03), silencio(0.06),
                           nota(150, 0.35, "cuadrada", 0.35)),
    # 6: campana
    "6": lambda: mezclar(nota(880, 1.2, vol=0.5, caida=1.15), nota(1760, 1.0, vol=0.2, caida=0.95),
                         nota(2640, 0.6, vol=0.1, caida=0.55)),
    # 7: claxon
    "7": lambda: secuencia(mezclar(nota(349, 0.18, "cuadrada", 0.3, caida=0.03),
                                   nota(440, 0.18, "cuadrada", 0.3, caida=0.03)),
                           silencio(0.06),
                           mezclar(nota(349, 0.4, "cuadrada", 0.3, caida=0.05),
                                   nota(440, 0.4, "cuadrada", 0.3, caida=0.05))),
    # 8: bombo
    "8": lambda: nota(lambda t: 45 + 110 * math.exp(-25 * t), 0.5, vol=0.9, caida=0.45),
    # 9: redoblante
    "9": lambda: mezclar(ruido(0.3, 0.6, 18.0), nota(190, 0.12, "triangulo", 0.4, caida=0.1)),
    # 0: bip
    "0": lambda: nota(1000, 0.3, vol=0.5, caida=0.05),
    # 000: fanfarria
    "000": lambda: secuencia(*[nota(f, d, "sierra", 0.35, caida=0.04) for f, d in
                               ((SOL / 2, 0.12), (DO, 0.12), (MI, 0.12), (SOL, 0.25),
                                (MI, 0.12), (SOL, 0.5))]),
    # . : clic
    "punto": lambda: nota(2500, 0.04, "cuadrada", 0.4, ataque=0.001, caida=0.03),
    # Enter: exito
    "enter": lambda: mezclar(nota(DO, 0.9, vol=0.4), secuencia(silencio(0.1), nota(MI, 0.8, vol=0.4)),
                             secuencia(silencio(0.2), nota(SOL, 0.7, vol=0.4)),
                             secuencia(silencio(0.3), nota(DO * 2, 0.6, vol=0.4))),
    # + : sirena que sube
    "mas": lambda: nota(lambda t: 500 + 600 * t + 80 * math.sin(2 * math.pi * 8 * t), 0.9, "triangulo", 0.5),
    # - : trombon triste
    "menos": lambda: secuencia(*[nota(lambda t, f=f: f * (1 - 0.03 * math.sin(2 * math.pi * 5 * t)),
                                      d, "sierra", 0.35, caida=0.05) for f, d in
                                 ((392, 0.3), (370, 0.3), (349, 0.3), (330, 0.7))]),
    # * : alarma de dos tonos
    "multiplicar": lambda: secuencia(*[nota(f, 0.15, "cuadrada", 0.3, caida=0.01)
                                       for f in (880, 660) * 3]),
    # / : boing
    "dividir": lambda: nota(lambda t: 200 + 250 * math.exp(-4 * t) * (1 + math.sin(2 * math.pi * 14 * t)),
                            0.7, vol=0.6),
    # Interruptor (Num Lock): encendido / apagado
    "on": lambda: secuencia(nota(880, 0.08, vol=0.5, caida=0.02), silencio(0.03),
                            nota(1320, 0.12, vol=0.5)),
    "off": lambda: secuencia(nota(1320, 0.08, vol=0.5, caida=0.02), silencio(0.03),
                             nota(660, 0.12, vol=0.5)),
}


def main():
    CARPETA.mkdir(exist_ok=True)
    print(f"Generando sonidos de prueba en {CARPETA}")
    for nombre, generador in SONIDOS.items():
        guardar(nombre, generador())
    print("Listo.")


if __name__ == "__main__":
    main()
