from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BASE = Path(__file__).resolve().parent
OUT = BASE / "openclaw_finanzas_presentacion_2026-03-11.pdf"


def money(v: str) -> str:
    return v


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverKicker", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#2B5F75"), alignment=TA_CENTER, spaceAfter=10))
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=colors.HexColor("#0B1F33"), alignment=TA_CENTER, spaceAfter=8))
styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=12, leading=16, textColor=colors.HexColor("#41566B"), alignment=TA_CENTER, spaceAfter=16))
styles.add(ParagraphStyle(name="SectionTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#12344D"), spaceBefore=4, spaceAfter=10))
styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=colors.HexColor("#1D2730"), alignment=TA_LEFT, spaceAfter=7))
styles.add(ParagraphStyle(name="DeckBullet", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.2, leading=13.5, leftIndent=14, bulletIndent=4, textColor=colors.HexColor("#1D2730"), spaceAfter=4))
styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.8, leading=11.5, textColor=colors.HexColor("#5A6B78"), spaceAfter=4))


def page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D7E1EA"))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, A4[1] - 1.5 * cm, A4[0] - doc.rightMargin, A4[1] - 1.5 * cm)
    canvas.line(doc.leftMargin, 1.2 * cm, A4[0] - doc.rightMargin, 1.2 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7A88"))
    canvas.drawString(doc.leftMargin, 0.7 * cm, "OpenClaw Finance Intelligence System")
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.7 * cm, f"Pagina {canvas.getPageNumber()}")
    canvas.restoreState()


story = []

story.append(Spacer(1, 3.2 * cm))
story.append(Paragraph("Presentacion ejecutiva confidencial", styles["CoverKicker"]))
story.append(Paragraph("OpenClaw Finance Intelligence System", styles["CoverTitle"]))
story.append(Paragraph("Infraestructura de inteligencia financiera multiagente, auditable y preparada para banca, family offices e inversores sofisticados.", styles["CoverSub"]))
story.append(Spacer(1, 0.5 * cm))

cover_table = Table(
    [
        ["Fecha", "2026-03-11"],
        ["Estado", "Sistema operativo en fase de simulacion avanzada y validacion"],
        ["Cobertura actual", "Activos digitales + expansion estructurada a USA/NASDAQ"],
        ["Tesis", "Mas control, mas explicabilidad, menos dependencia de cajas negras"],
    ],
    colWidths=[4.2 * cm, 11.2 * cm],
)
cover_table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F8FB")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#23313F")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E1EA")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#B7C7D6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
    )
)
story.append(cover_table)
story.append(Spacer(1, 0.8 * cm))
story.append(Paragraph("OpenClaw no es un bot mas. Es una plataforma de decision financiera con especializacion por agente, trazabilidad de tesis, gobierno de riesgo y una cabina operativa lista para supervision profesional.", styles["Body"]))
story.append(PageBreak())


def section(title, intro=None, bullets=None):
    story.append(Paragraph(title, styles["SectionTitle"]))
    if intro:
        story.append(Paragraph(intro, styles["Body"]))
    if bullets:
        for bullet in bullets:
            story.append(Paragraph(bullet, styles["DeckBullet"], bulletText="-"))
    story.append(Spacer(1, 0.15 * cm))


section(
    "1. Problema y oportunidad",
    "La mayor parte del software financiero de nueva generacion falla por el mismo punto: promete inteligencia, pero no resuelve gobernanza, explicabilidad ni operacion. OpenClaw se construye desde esos puntos criticos.",
    [
        "Las cajas negras generan rechazo en banca y comites de inversion.",
        "Los stacks premium elevan mucho el coste de experimentacion y despliegue.",
        "Los bots simples reaccionan al precio; no orquestan contexto macro, capital, tecnico y riesgo.",
        "Muchos proyectos venden ML sin ensenar logs, entrenamiento, versionado ni comparativas reales.",
    ],
)

section(
    "2. Que ofrece OpenClaw",
    None,
    [
        "Sistema multiagente con especializacion funcional y regla de convergencia.",
        "Motor cuantitativo con LSTM real, reentreno y registro de modelos champion.",
        "Capa de riesgo con limites, pausa, slippage, fees, kill switch y simulacion controlada.",
        "Dashboard operativo con vistas de finanzas, LSTM, SysAdmin, Terminal y Control Hub.",
        "Coste contenido gracias a mezcla de fuentes abiertas, automatizacion local y modularidad.",
    ],
)

section(
    "3. Arquitectura multiagente",
    "La arquitectura evita que una sola fuente mande sobre la decision. Cada agente aporta una capa distinta de verdad.",
    [
        "L-Scanner: macro liquidez, balances y M2 como radar de flujo estructural.",
        "I-Watcher: compras insider y senales de capital con conviccion real.",
        "T-Analyst: validacion tecnica, niveles, timing y estructura.",
        "Macro / News / Social scanners: calendario, catalizadores, sentimiento y rotacion.",
        "Alpha Scout / Claw-Prime: orquestacion final y emision de CLAW CARD accionable.",
    ],
)

story.append(PageBreak())

section(
    "4. Decision por convergencia, no por intuicion",
    "El sistema no autoriza una idea por una sola senal. Exige una estructura que se parece mucho mas a una mesa profesional que a un bot retail.",
    [
        "Senal estructural: spinoff, guidance, catalizador o inflexion operativa.",
        "Senal de capital: insiders, opciones, flujos o rotacion.",
        "Senal tecnica: EMA, RSI, Bollinger, volumen, ruptura o base.",
        "Capa de riesgo: invalidacion, tamano, stop y horizonte temporal.",
        "Estados operativos: WATCH, READY, TRIGGERED e INVALIDATED.",
    ],
)

section(
    "5. Explicabilidad util para banca e inversores",
    "Cada tesis se puede empaquetar en una CLAW CARD: setup, catalizador, confirmaciones, riesgos, invalidacion y plan. Esto simplifica compliance, comites y auditoria posterior.",
)

metrics = Table(
    [
        ["Bloque", "Estado actual"],
        ["Historico real", "Pipeline multi-activo con datos reales"],
        ["Entrenamiento", "LSTM real con reentreno diario incremental"],
        ["Versionado", "Champion model y metadatos por simbolo"],
        ["Evaluacion", "Walk-forward proxy y baseline vs LSTM"],
        ["Observabilidad", "Logs reales y vista dedicada LSTM Real"],
    ],
    colWidths=[5.4 * cm, 10 * cm],
)
metrics.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14324A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CFDCE7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("PADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]
    )
)
story.append(metrics)
story.append(Spacer(1, 0.25 * cm))
story.append(Paragraph("El mensaje mas importante no es que haya ML. El mensaje importante es que el ML ya esta gobernado y se compara contra baseline. Eso es lo que diferencia un activo serio de una demo bonita.", styles["Body"]))

section(
    "6. Evidencia cuantitativa disponible",
    None,
    [
        "BTCUSDT: mejor val_mse registrado de 1.609e-05.",
        "SOLUSDT: mejor val_mse registrado de 8.502e-05.",
        "Walk-forward proxy: BTC 0.500 frente a baseline 0.479.",
        "Walk-forward proxy: SOL 0.493 frente a baseline 0.478.",
        "Monitor reciente de simulacion: win rate 58.35%, expectancy 0.6335 USD/trade, semaforo VERDE.",
    ],
)

story.append(PageBreak())

section(
    "7. Riesgo, guardarrailes y fase actual",
    "OpenClaw esta mejor preparado que muchas alternativas porque no confunde investigacion con ejecucion real. La fase actual es sim_only por diseno.",
    [
        "Riesgo por operacion: 1.0%.",
        "Maxima perdida diaria: 5.0%.",
        "Pausa tras 3 perdidas consecutivas.",
        "Slippage: 5 bps. Fees: 10 bps.",
        "Universo inicial permitido: BTCUSDT y SOLUSDT.",
        "Kill switch, pausa manual y control desde dashboard.",
    ],
)

section(
    "8. Operacion y observabilidad",
    None,
    [
        "Dashboard financiero principal para supervision funcional.",
        "LSTM Real para entrenamiento, estado, historicos y logs.",
        "SysAdmin para puertos, gateway, tareas programadas y salud del stack.",
        "Terminal para telemetria y comandos de soporte.",
        "Control Hub unificado en una sola URL con pestañas.",
    ],
)

section(
    "9. Por que es mejor que la mayoria de alternativas",
    "La posicion comercial mas solida no es afirmar superioridad absoluta, sino mostrar ventajas que un comprador sofisticado pueda verificar.",
    [
        "Mas explicable que una IA generica conectada a noticias.",
        "Mas gobernable que un bot de trading tradicional.",
        "Mas barato de validar que muchos stacks cuantitativos premium.",
        "Mas modular y personalizable que soluciones cerradas de proveedor unico.",
        "Mas defendible ante comite porque combina tesis, riesgo, estado y evidencias.",
    ],
)

section(
    "10. Encaje comercial",
    None,
    [
        "Research augmentation para analistas y PMs.",
        "Radar de oportunidades asimetricas en digital assets y growth equities.",
        "Cockpit interno para scoring de watchlists y memos de inversion.",
        "Plataforma white-label para banco, fondo o family office.",
        "Licenciamiento por modulos o partnership con datos propios del comprador.",
    ],
)

story.append(PageBreak())

section(
    "11. Mensaje final para comprador",
    "OpenClaw convierte la IA financiera en una infraestructura de decision con explicacion, control, observabilidad y capacidad de evolucion institucional.",
    [
        "No vende magia: vende proceso defendible.",
        "No depende de una sola senal: exige convergencia.",
        "No es un modelo suelto: es una plataforma completa.",
        "No es una demo opaca: ya tiene logs, gobierno y supervision operativa.",
        "No promete ciegamente resultados: muestra fase, limites y roadmap.",
    ],
)

story.append(Spacer(1, 0.3 * cm))
story.append(Paragraph("Conclusión ejecutiva: para un comprador serio, el valor de OpenClaw no esta solo en el edge potencial. Esta en haber convertido ese edge en un sistema presentable, auditable y escalable.", styles["Body"]))
story.append(Spacer(1, 0.4 * cm))
story.append(Paragraph("Nota de integridad comercial: las metricas actuales corresponden a una fase de simulacion avanzada y validacion. Precisamente por eso existe una oportunidad de compra temprana sobre una base ya funcional, con gran margen de mejora y personalizacion institucional.", styles["Small"]))


doc = SimpleDocTemplate(
    str(OUT),
    pagesize=A4,
    leftMargin=1.7 * cm,
    rightMargin=1.7 * cm,
    topMargin=2.2 * cm,
    bottomMargin=1.8 * cm,
)
doc.build(story, onFirstPage=page, onLaterPages=page)
print(str(OUT))
