"""Segmentos básicos de autopista. Unidades internas: ft, mi/h, pc/h/carril.

HCM 2010, capítulo 11, Exhibits 11-3, 11-5, 11-8, 11-9 y 11-10.
El modo curso reproduce S=FFS de las diapositivas; no se extrapola a congestión.
"""
from dataclasses import dataclass, asdict
from math import floor, isfinite

TERRENOS = {"Llano": (1.5, 1.2), "Ondulado": (2.5, 2.0), "Montañoso": (4.5, 4.0)}
# FFS: (punto de quiebre, coeficiente cuadrático, capacidad)
CURVAS = {55: (1800, .00002469, 2250), 60: (1600, .00001816, 2300),
          65: (1400, .00001418, 2350), 70: (1200, .00001160, 2400),
          75: (1000, .00001107, 2400)}

@dataclass(frozen=True)
class Entrada:
    ancho: float = 11.0
    lateral: float = 2.0
    carriles: int = 2
    rampas: float = 4.0
    volumen: float = 2000.0
    phf: float = .92
    camiones: float = 5.0
    buses: float = 0.0
    recreativos: float = 0.0
    terreno: str = "Ondulado"
    fp: float = 1.0

class DatosInvalidos(ValueError):
    pass

def validar(e):
    errores = []
    for k, v in asdict(e).items():
        if k != "terreno" and (not isinstance(v, (int, float)) or not isfinite(v)):
            errores.append(f"{k}: ingresa un número finito.")
    if errores:
        raise DatosInvalidos(" ".join(errores))
    if e.ancho <= 0:
        errores.append("El ancho de carril debe ser mayor que cero.")
    if e.lateral < 0:
        errores.append("La distancia libre lateral no puede ser negativa.")
    if e.carriles < 2 or e.carriles != int(e.carriles):
        errores.append("Se requieren al menos 2 carriles enteros por sentido. Una vía de dos carriles totales requiere otro procedimiento.")
    if e.rampas < 0 or e.volumen < 0:
        errores.append("Volumen y densidad de rampas no pueden ser negativos.")
    if not .25 <= e.phf <= 1:
        errores.append("PHF debe estar entre 0.25 y 1, para cuatro intervalos de 15 minutos.")
    if not .85 <= e.fp <= 1:
        errores.append("El factor de conductores debe estar entre 0.85 y 1.")
    if any(not 0 <= p <= 100 for p in (e.camiones, e.buses, e.recreativos)) or e.camiones+e.buses+e.recreativos > 100:
        errores.append("Los porcentajes deben estar entre 0 y 100 y sumar como máximo 100 %.")
    if e.terreno not in TERRENOS:
        errores.append("Selecciona un terreno válido.")
    if errores:
        raise DatosInvalidos(" ".join(errores))

def ajuste_lateral(lateral, carriles):
    """Interpolación lineal de Exhibit 11-9; ≥6 ft sin reducción."""
    return max(0, 6-lateral) * {2:.6, 3:.4, 4:.2, 5:.1}[min(carriles, 5)]

def nivel_densidad(d):
    for limite, nivel in ((11,"A"), (18,"B"), (26,"C"), (35,"D"), (45,"E")):
        if d <= limite:
            return nivel
    return "F"

def velocidad(vp, curva):
    bp, a, c = CURVAS[curva]
    if not 0 <= vp <= c:
        raise DatosInvalidos("La curva de velocidad solo se aplica entre flujo cero y capacidad.")
    return float(curva) if vp <= bp else curva-a*(vp-bp)**2

def calcular(e, modo="hcm"):
    validar(e)
    if modo not in ("hcm", "curso"):
        raise DatosInvalidos("Modo de cálculo desconocido.")
    # Intervalos de ancho de carril, sin interpolación.
    # Para 0 < ancho < 10 ft se extiende 6.6 por criterio personalizado.
    if e.ancho >= 12:
        flw = 0.0
    elif e.ancho >= 11:
        flw = 1.9
    else:
        flw = 6.6
    flc = ajuste_lateral(e.lateral, e.carriles)
    fr = 3.22*e.rampas**.84
    ffs = 75.4-flw-flc-fr
    if not 52.5 <= ffs < 77.5:
        raise DatosInvalidos(f"FFS = {ffs:.2f} mi/h fuera del intervalo de selección de curvas implementado [52.5, 77.5). Revisa la geometría y la densidad de rampas.")
    curva = int(5*floor(ffs/5+.5))
    bp, a, cap = CURVAS[curva]
    et, er = TERRENOS[e.terreno]
    fhv = 100/(100+e.camiones*(et-1)+e.buses*(et-1)+e.recreativos*(er-1))
    vp = e.volumen/(e.phf*e.carriles*fhv*e.fp)
    excede = vp > cap
    # No se calcula una densidad ficticia con demanda superior a capacidad.
    s = None if excede else (velocidad(vp, curva) if modo == "hcm" else ffs)
    d = None if s is None else vp/s
    # Los coeficientes publicados están redondeados. A capacidad, su densidad
    # puede superar 45 por unas centésimas; no implica sobresaturación.
    los = "F" if excede else nivel_densidad(d)
    if modo == "hcm" and not excede and los == "F":
        los = "E"
    return dict(flw=flw, flc=flc, fr=fr, ffs=ffs, curva=curva, bp=bp, a=a,
                capacidad=cap, et=et, eb=et, er=er, fhv=fhv, vp=vp,
                velocidad=s, densidad=d, los=los, excede=excede,
                vc=vp/cap, capacidad_veh=cap*e.phf*e.carriles*fhv*e.fp,
                modo=modo, supuesto_curso=(modo == "curso" and vp > bp),
                ancho_personalizado=(e.ancho < 10))
