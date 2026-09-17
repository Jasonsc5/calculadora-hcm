from dataclasses import asdict
import html
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from calculos import Entrada, DatosInvalidos, TERRENOS, CURVAS, calcular, velocidad

st.set_page_config(page_title="Vía · Nivel de servicio", page_icon="🛣️", layout="wide")
st.markdown('''<style>
.block-container{max-width:1440px;padding-top:4.5rem;padding-bottom:2rem}
h1{font-size:2.2rem!important;letter-spacing:-.065rem} h3{font-size:1.2rem!important}
[data-testid="stVerticalBlockBorderWrapper"]>div{background:white;border-radius:14px}
div[data-testid="stMetric"]{background:#edf3fb;padding:14px;border-radius:10px}
div[data-testid="stMetricValue"]{font-size:1.7rem}
button[data-baseweb="tab"]{font-size:1rem;padding:12px 20px}
.eyebrow{font-size:13px;letter-spacing:.14em;font-weight:700;color:#1763e8;margin-bottom:8px}
.result{display:flex;align-items:center;gap:18px;padding:20px;border:1px solid #dce4ef;border-radius:12px;background:#fff;margin:8px 0 18px}
.grade{font-size:3rem;font-weight:750;border-radius:12px;width:78px;min-width:78px;text-align:center;padding:2px 0}
.result-title{font-size:1.12rem;font-weight:700}.result-note{color:#52657a;font-size:14px;margin-top:4px}
.step{font-size:14px;font-weight:700;color:#1763e8;text-transform:uppercase;letter-spacing:.04em;margin-top:8px}
.foot{font-size:13px;color:#52657a;border-top:1px solid #dce4ef;padding-top:16px;margin-top:24px}
@media(max-width:640px){.block-container{padding:4.5rem 1rem 1rem}h1{font-size:1.7rem!important}.result{padding:12px}}
</style>''', unsafe_allow_html=True)

COLORS = {"A":"#176443", "B":"#287846", "C":"#1d5dab", "D":"#956000", "E":"#a34a10", "F":"#b42335"}
NOTES = {"A":"Amplia libertad de maniobra.","B":"Buena libertad de maniobra.","C":"La interacción entre vehículos comienza a limitar las maniobras.","D":"Libertad de maniobra considerablemente restringida.","E":"Operación próxima a la capacidad.","F":"Demanda superior a la capacidad del segmento."}

def preset(mathcad=False):
    a = asdict(Entrada())
    st.session_state["two"] = mathcad
    st.session_state["metrico"] = False
    st.session_state["modo"] = "Ejemplo del curso" if not mathcad else "HCM 2010"
    if mathcad:
        a.update(ancho=9.0,lateral=3.5,rampas=4.0,phf=.95,camiones=20.0,recreativos=11.0,terreno="Montañoso",volumen=5870.0)
    for idx in range(2):
        for k,v in a.items():
            st.session_state[f"{idx}_{k}"] = 7345.0 if mathcad and idx==1 and k=="volumen" else v

def change_units():
    factor = .3048 if st.session_state["metrico"] else 1/.3048
    ramp_factor = 1/1.609344 if st.session_state["metrico"] else 1.609344
    for idx in range(2):
        for k in ("ancho", "lateral"):
            key=f"{idx}_{k}"
            if key in st.session_state:
                st.session_state[key] *= factor
        key=f"{idx}_rampas"
        if key in st.session_state:
            st.session_state[key] *= ramp_factor

def number(label, idx, name, default, **kwargs):
    key=f"{idx}_{name}"
    if key not in st.session_state:
        st.session_state[key]=default
    return st.number_input(label, key=key, **kwargs)

def inputs(idx, metric):
    unit="m" if metric else "ft"
    f=.3048 if metric else 1
    st.markdown('<div class="step">01 · Geometría</div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    with a:
        n=number("Carriles por sentido",idx,"carriles",2,min_value=1,max_value=12,step=1,help="No ingreses el total de ambos sentidos.")
        w=number(f"Ancho de carril ({unit})",idx,"ancho",11.0*f,min_value=0.,max_value=30.,step=.1 if metric else .5,format="%.3f")
    with b:
        l=number(f"Distancia libre lateral ({unit})",idx,"lateral",2.0*f,min_value=0.,max_value=100.,step=.1 if metric else .5,format="%.3f",help="Distancia hasta el obstáculo lateral a la derecha; no siempre coincide con todo el ancho de berma.")
        r=number("Rampas/km" if metric else "Rampas/milla",idx,"rampas",4./1.609344 if metric else 4.,min_value=0.,max_value=100.,step=.1,format="%.4f",help="Entradas y salidas por unidad de longitud. Para el procedimiento: contar en 6 millas (3 a cada lado del centro) y dividir entre 6.")
    st.markdown('<div class="step">02 · Demanda y conductores</div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    with a:
        v=number("Volumen (veh/h/sentido)",idx,"volumen",2000.0,min_value=0.,max_value=100000.,step=100.,format="%.0f")
        phf=number("Factor de hora punta · PHF",idx,"phf",.92,min_value=.25,max_value=1.,step=.01,format="%.2f")
    with b:
        if f"{idx}_terreno" not in st.session_state: st.session_state[f"{idx}_terreno"]="Ondulado"
        terrain=st.selectbox("Tipo de terreno",list(TERRENOS),key=f"{idx}_terreno")
        fp=number("Factor de conductores · fp",idx,"fp",1.,min_value=.85,max_value=1.,step=.01,format="%.2f",help="1.00 para conductores habituales.")
    with st.expander("03 · Composición vehicular",expanded=True):
        a,b,c=st.columns(3)
        with a: pt=number("Camiones (%)",idx,"camiones",5.,min_value=0.,max_value=100.,step=1.,format="%.1f")
        with b: pb=number("Buses (%)",idx,"buses",0.,min_value=0.,max_value=100.,step=1.,format="%.1f")
        with c: pr=number("Recreativos (%)",idx,"recreativos",0.,min_value=0.,max_value=100.,step=1.,format="%.1f",help="RV: vehículos recreacionales. No equivale a todas las vans.")
        st.caption(f"Vehículos ligeros: {max(0,100-pt-pb-pr):.1f} % · Los equivalentes se seleccionan por terreno.")
    return Entrada(w/f,l/f,n,r*1.609344 if metric else r,v,phf,pt,pb,pr,terrain,fp)

def result_card(name, r):
    grade=r['los']; color=COLORS[grade]
    if r['ancho_personalizado']:
        st.warning("Criterio personalizado activo: para ancho < 10 ft se adopta fLW = 6.6 mi/h. La tabla HCM mostrada no cubre ese intervalo.")
    st.markdown(f'''<div class="result"><div class="grade" style="color:{color};background:{color}12">{grade}</div><div><div class="result-title">{html.escape(name)} · Nivel de servicio {grade}</div><div class="result-note">{NOTES[grade]}</div></div></div>''',unsafe_allow_html=True)
    a,b,c=st.columns(3)
    a.metric("Densidad · pc/mi/carril","—" if r['densidad'] is None else f"{r['densidad']:.2f}")
    b.metric("Velocidad · mi/h","—" if r['velocidad'] is None else f"{r['velocidad']:.2f}")
    c.metric("Demanda / capacidad",f"{r['vc']:.2f}")
    if r['excede']:
        st.error(f"Demanda equivalente {r['vp']:,.1f} > capacidad {r['capacidad']:,.0f} pc/h/carril. No se extrapolan velocidad ni densidad con las curvas de flujo estable.")
    elif r['supuesto_curso']:
        st.warning("Resultado simplificado: el flujo supera el punto de quiebre de la curva. Cambia a HCM 2010 para considerar la reducción de velocidad.")
    st.caption(f"FFS estimada: {r['ffs']:.2f} mi/h · Curva seleccionada: {r['curva']} mi/h · fHV: {r['fhv']:.4f}")

def chart(r):
    fig=go.Figure()
    cap=r['capacidad']; curve=r['curva']
    xs=[cap*i/100 for i in range(101)]
    ys=[velocidad(x,curve) for x in xs]
    fig.add_trace(go.Scatter(x=xs,y=ys,name=f"Curva HCM · {curve} mi/h",mode="lines",line=dict(color="#1763e8",width=3)))
    if not r['excede']:
        fig.add_trace(go.Scatter(x=[r['vp']],y=[r['velocidad']],name="Punto calculado",mode="markers",marker=dict(size=13,color=COLORS[r['los']],line=dict(color="white",width=2))))
    fig.add_vline(x=cap,line_dash="dot",line_color="#8293aa",annotation_text="Capacidad",annotation_position="top left")
    fig.update_layout(height=260,margin=dict(l=5,r=15,t=25,b=5),paper_bgcolor="white",plot_bgcolor="white",font=dict(family="Arial",size=13,color="#52657a"),showlegend=False,xaxis_title="Flujo equivalente (pc/h/carril)",yaxis_title="Velocidad (mi/h)",xaxis=dict(range=[0,2500],gridcolor="#eef2f6"),yaxis=dict(range=[40,80],gridcolor="#eef2f6"))
    st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})

def procedure(name,e,r):
    st.subheader(name)
    with st.container(border=True):
        st.markdown("**1. Factores geométricos y velocidad libre**")
        st.write(f"Ancho: {e.ancho:.3f} ft → fLW = {r['flw']:.2f} mi/h. Distancia lateral: {e.lateral:.3f} ft; {e.carriles} carriles → fLC = {r['flc']:.2f} mi/h.")
        if r['ancho_personalizado']:
            st.warning("Ancho menor de 10 ft: fLW = 6.6 mi/h por criterio personalizado del usuario, fuera del intervalo de la tabla original.")
        st.caption("La distancia lateral se interpola linealmente entre las filas de la tabla; con 6 ft o más, el ajuste es cero.")
        st.latex(r"FFS=75.4-f_{LW}-f_{LC}-3.22\,TRD^{0.84}")
        st.latex(fr"FFS=75.4-{r['flw']:.2f}-{r['flc']:.2f}-3.22({e.rampas:.4f})^{{0.84}}={r['ffs']:.3f}\;\mathrm{{mi/h}}")
        st.write(f"Curva HCM seleccionada: **{r['curva']} mi/h**. Punto de quiebre: **{r['bp']} pc/h/carril**. Capacidad: **{r['capacidad']} pc/h/carril**.")
    with st.container(border=True):
        st.markdown("**2. Vehículos pesados y tasa de flujo**")
        st.write(f"Terreno {e.terreno.lower()}: ET = EB = {r['et']}; ER = {r['er']}. Porcentajes ingresados como 5 para 5 %, no como 0.05.")
        st.latex(r"f_{HV}=\frac{100}{100+P_T(E_T-1)+P_B(E_B-1)+P_R(E_R-1)}")
        st.latex(fr"f_{{HV}}=\frac{{100}}{{100+{e.camiones:g}({r['et']:g}-1)+{e.buses:g}({r['eb']:g}-1)+{e.recreativos:g}({r['er']:g}-1)}}={r['fhv']:.6f}")
        st.latex(r"v_p=\frac{V}{PHF\,N\,f_{HV}\,f_p}")
        st.latex(fr"v_p=\frac{{{e.volumen:g}}}{{{e.phf:g}\times{e.carriles}\times{r['fhv']:.6f}\times{e.fp:g}}}={r['vp']:.3f}\;\mathrm{{pc/h/carril}}")
    with st.container(border=True):
        st.markdown("**3. Capacidad, velocidad y densidad**")
        st.write(f"Relación demanda/capacidad = {r['vp']:.3f}/{r['capacidad']} = **{r['vc']:.4f}**.")
        if r['excede']:
            st.error("La demanda excede la capacidad: nivel F. Las curvas de flujo estable no permiten obtener aquí una velocidad ni una densidad operacional.")
        else:
            if r['modo']=="curso":
                st.write("Modo del curso: se asume S = FFS sin redondear. Es una simplificación, no la aplicación completa de la curva HCM.")
            else:
                st.latex(fr"S=\begin{{cases}}{r['curva']},&v_p\leq {r['bp']}\\ {r['curva']}-{r['a']:.8f}(v_p-{r['bp']})^2,&{r['bp']}<v_p\leq {r['capacidad']}\end{{cases}}")
            st.latex(fr"D=\frac{{v_p}}{{S}}=\frac{{{r['vp']:.3f}}}{{{r['velocidad']:.3f}}}={r['densidad']:.3f}\;\mathrm{{pc/mi/carril}}")
            st.write(f"Equivalencias: S = {r['velocidad']*1.609344:.2f} km/h; D = {r['densidad']/1.609344:.3f} pc/km/carril.")
            if r['supuesto_curso']: st.warning("El supuesto S = FFS omite la reducción de velocidad correspondiente a este flujo.")
        st.success(f"Resultado: nivel de servicio {r['los']}.")
        st.caption("Los cálculos conservan todos los decimales. El redondeo visible no se reutiliza en las operaciones.")

st.markdown('<div class="eyebrow">VÍA / ANÁLISIS DE TRÁNSITO</div>',unsafe_allow_html=True)
st.title("Nivel de servicio en autopistas")
st.caption("Segmentos básicos · HCM 2010 · Geometría, demanda y resultados por sentido")

top=st.columns([2,1,1],vertical_alignment="bottom")
with top[0]: selected=st.selectbox("Procedimiento",["HCM 2010","Ejemplo del curso"],key="modo")
with top[1]: st.button("Cargar ejemplo del curso",on_click=preset,width="stretch")
with top[2]: st.button("Cargar datos de Mathcad",on_click=preset,args=(True,),width="stretch")
if selected=="Ejemplo del curso":
    st.info("Modo del curso: reproduce D = vp / FFS de las diapositivas. La capacidad se verifica antes de calcular densidad. Usa HCM 2010 para aplicar las curvas de velocidad.")

tab_calc,tab_steps,tab_tables=st.tabs(["Calculadora","Procedimiento","Tablas de referencia"])
entries=[]; results=[]; errors=[]; names=[]
with tab_calc:
    left,right=st.columns([1.05,1],gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Datos de entrada")
            a,b=st.columns(2)
            with a: metric=st.toggle("Ingresar longitudes en metros",key="metrico",on_change=change_units)
            with b: two=st.toggle("Analizar dos sentidos",key="two")
            names=["Oeste","Este"] if two else ["Sentido analizado"]
            if two:
                input_tabs=st.tabs(names)
                for idx,t in enumerate(input_tabs):
                    with t: entries.append(inputs(idx,metric))
            else: entries.append(inputs(0,metric))
            st.caption("Los resultados se actualizan al confirmar cada entrada con Enter o al salir del campo.")
    for e in entries:
        try:
            results.append(calcular(e,"hcm" if selected=="HCM 2010" else "curso")); errors.append(None)
        except DatosInvalidos as ex:
            results.append(None);errors.append(str(ex))
    with right:
        st.subheader("Resultados")
        for name,r,err in zip(names,results,errors):
            if err:
                st.error(f"{name}: {err}")
                st.caption("Corrige los datos indicados para obtener un resultado.")
            else: result_card(name,r)
        valid=[(name,r) for name,r in zip(names,results) if r]
        if valid:
            name,r=valid[0]
            with st.container(border=True):
                st.markdown(f"**Curva velocidad–flujo · {name}**")
                chart(r)
                st.caption("La curva corresponde al HCM. En el modo del curso el punto usa S = FFS; por ello puede separarse de la curva.")
            rows=[]
            for name,r in valid:
                rows.append({"Sentido":name,"Nivel":r['los'],"vp (pc/h/carril)":round(r['vp'],2),"Capacidad (pc/h/carril)":r['capacidad'],"D (pc/mi/carril)":None if r['densidad'] is None else round(r['densidad'],3),"Criterio de ancho":"Personalizado: ancho < 10 ft, fLW = 6.6" if r['ancho_personalizado'] else "Tabla HCM"})
            if two: st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
            st.download_button("Descargar resultados CSV",pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),"resultados_hcm.csv","text/csv",width="stretch")

with tab_steps:
    st.subheader("Memoria de cálculo")
    st.caption("Datos convertidos a unidades del procedimiento original. El desarrollo coincide con los valores actuales de la calculadora.")
    for name,e,r,err in zip(names,entries,results,errors):
        if err: st.error(f"{name}: {err}")
        else: procedure(name,e,r)
    payload={"procedimiento":selected,"unidades_internas":"ft, mi/h, rampas/mi, veh/h/sentido, porcentajes 0–100","sentidos":[dict(nombre=n,entrada=asdict(e),resultado=r,error=err) for n,e,r,err in zip(names,entries,results,errors)]}
    st.download_button("Descargar datos y cálculo JSON",json.dumps(payload,ensure_ascii=False,indent=2),"calculo_hcm.json","application/json")

with tab_tables:
    st.subheader("Factores y criterios utilizados")
    a,b=st.columns(2)
    with a:
        st.markdown("**Ancho de carril · fLW**")
        st.table(pd.DataFrame({"Ancho (ft)":["0 < ancho < 10","10 ≤ ancho < 11","11 ≤ ancho < 12","ancho ≥ 12"],"Reducción (mi/h)":[6.6,6.6,1.9,0.0],"Criterio":["Personalizado","Tabla HCM","Tabla HCM","Tabla HCM"]}))
        st.caption("Ancho de carril: factores por intervalos, sin interpolación. La extensión a anchos menores de 10 ft es un criterio personalizado.")
        st.markdown("**Equivalentes por terreno**")
        st.table(pd.DataFrame([{"Terreno":k,"Camión / bus":v[0],"Recreativo":v[1]} for k,v in TERRENOS.items()]))
    with b:
        st.markdown("**Distancia libre lateral · fLC (mi/h)**")
        st.table(pd.DataFrame({"Distancia (ft)":["≥6","5","4","3","2","1","0"],"2 carriles":[0,.6,1.2,1.8,2.4,3,3.6],"3 carriles":[0,.4,.8,1.2,1.6,2,2.4],"4 carriles":[0,.2,.4,.6,.8,1,1.2],"≥5 carriles":[0,.1,.2,.3,.4,.5,.6]}))
        st.caption("Para distancias intermedias se aplica interpolación lineal. Carriles contados por sentido.")
    st.markdown("**Niveles de servicio**")
    st.table(pd.DataFrame({"Nivel":list("ABCDEF"),"Densidad (pc/mi/carril)":["≤11",">11 a 18",">18 a 26",">26 a 35",">35 a 45","Demanda > capacidad / flujo forzado"]}))
    with st.expander("Alcance, curvas y fuentes"):
        st.write("Aplicación para segmentos básicos de autopista, con dos o más carriles por sentido y terreno general. No implementa zonas de entrecruzamiento, rampas de incorporación/salida, pendientes específicas, incidentes, colas aguas abajo ni ajustes meteorológicos. Los factores para terreno general no sustituyen el análisis de una pendiente específica.")
        st.write("HCM 2010, capítulo 11: Exhibit 11-3 (curvas), 11-5 (LOS), 11-8 (ancho), 11-9 (lateral), 11-10 (equivalentes). FFS se redondea al múltiplo de 5 mi/h más cercano, con mitades hacia arriba, dentro de 52.5 ≤ FFS < 77.5 mi/h.")
        st.table(pd.DataFrame([{"Curva (mi/h)":k,"Quiebre":v[0],"Coeficiente a":v[1],"Capacidad":v[2]} for k,v in CURVAS.items()]))
        st.caption("A capacidad, los coeficientes redondeados de las curvas pueden producir una densidad unas centésimas mayor que 45. En ese caso se conserva el nivel E si la demanda no excede la capacidad.")
        st.markdown("[Manual HCM 2010 — copia consultada](https://www.jpautoceste.ba/wp-content/uploads/2022/05/Highway-Capacity-Manual-2010-PDFDrive-.pdf) · [FHWA: cálculo de medidas de desempeño](https://ops.fhwa.dot.gov/publications/fhwahop08054/sect4.htm)")
        st.write("El modo del curso conserva el supuesto S = FFS de las capturas proporcionadas. El ejemplo original obtiene C en ambos modos; la densidad difiere por la selección de la curva y por el redondeo de las diapositivas.")

st.markdown('<div class="foot">pc = automóvil equivalente · FFS = velocidad de flujo libre · N = carriles por sentido<br>Herramienta académica con alcance explícito; los resultados dependen de que el tramo cumpla las condiciones del procedimiento.</div>',unsafe_allow_html=True)
