# -*- coding: utf-8 -*-
"""
Comando de gestión: exportar reservas a Excel.

Genera un Excel multi-hoja listo para entregar a la gestoría o para las
cuentas mensuales de turismo de Lucía, con las columnas del Excel original:

Hoja 1 - Reservas del mes:
  Fecha actividad, Plataforma, Nº personas, Nombre cliente, Importe actividad,
  Cobrado, % Lucía, Recogida en coche, Precio recogida, Monitor recogida,
  Monitor experiencia, Total experiencia, Pago a otros, Código reserva,
  Estado, Teléfono, Email, Nacionalidad, Edades, Transporte, Dirección alojamiento

Hoja 2 - Resumen por plataforma:
  Plataforma, Nº reservas, Total personas, Total cobrado, Total experiencia

Hoja 3 - Resumen mensual:
  Total mes cobrado, Total personas, Total neto, Total transporte, Total Otros

Uso:
    python manage.py exportar_excel --mes 11 --anio 2026
    python manage.py exportar_excel --mes 11 --anio 2026 --salida reservas_noviembre_2026.xlsx
"""

import logging
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from django.utils import timezone

from reservas.models import Reserva, Plataforma, EstadoReserva

logger = logging.getLogger(__name__)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    OPENPYXL_DISPONIBLE = True
except ImportError:
    OPENPYXL_DISPONIBLE = False


class Command(BaseCommand):
    help = "Exporta reservas de un mes a Excel para las cuentas de turismo"

    def add_arguments(self, parser):
        parser.add_argument("--mes", type=int, required=True, help="Mes (1-12)")
        parser.add_argument("--anio", type=int, required=True, help="Año (ej. 2026)")
        parser.add_argument(
            "--salida",
            type=str,
            default=None,
            help="Ruta del archivo de salida (por defecto: reservas_<mes>_<anio>.xlsx)",
        )

    def handle(self, *args, **options):
        mes = options["mes"]
        anio = options["anio"]
        salida = options["salida"]

        if not 1 <= mes <= 12:
            self.stderr.write(self.style.ERROR("El mes debe estar entre 1 y 12."))
            return

        if not salida:
            salida = f"reservas_{mes:02d}_{anio}.xlsx"

        # Filtrar reservas del mes
        reservas = (
            Reserva.objects.filter(
                fecha_actividad__year=anio,
                fecha_actividad__month=mes,
            )
            .select_related("plataforma", "estado", "punto_recogida")
            .order_by("fecha_actividad", "hora_actividad")
        )

        if not OPENPYXL_DISPONIBLE:
            self.stderr.write(
                self.style.ERROR(
                    "openpyxl no instalado. Ejecuta: pip install openpyxl\n"
                    "O instala todos los requisitos: pip install -r requirements.txt"
                )
            )
            return

        wb = Workbook()

        # ==================================================================
        # Hoja 1: Reservas del mes
        # ==================================================================
        ws1 = wb.active
        ws1.title = f"Reservas {mes:02d}-{anio}"

        cabeceras = [
            "Fecha Actividad",
            "Plataforma",
            "Nº de personas",
            "Nombre cliente",
            "Importe de actividad",
            "Cobrado",
            "Porcentaje Lucia",
            "Recogida en coche",
            "Precio recogida",
            "Monitor recogida",
            "Monitor experiencia",
            "Total experiencia",
            "Pago a otros",
            "Cod. Reserva",
            "Estado",
            "Teléfono",
            "Correo",
            "Nacionalidad",
            "Edades",
            "Quiere transporte",
            "Dirección alojamiento",
        ]

        # Estilo de cabecera
        font_negrita = Font(bold=True, color="FFFFFF")
        relleno_azul = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        alineacion_centro = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for col_idx, cabecera in enumerate(cabeceras, start=1):
            celda = ws1.cell(row=1, column=col_idx, value=cabecera)
            celda.font = font_negrita
            celda.fill = relleno_azul
            celda.alignment = alineacion_centro

        fila = 2
        for r in reservas:
            ws1.cell(row=fila, column=1, value=r.fecha_actividad.strftime("%d/%m/%Y"))
            ws1.cell(row=fila, column=2, value=r.plataforma.nombre if r.plataforma else "")
            ws1.cell(row=fila, column=3, value=r.numero_personas)
            ws1.cell(row=fila, column=4, value=r.nombre_cliente)
            ws1.cell(row=fila, column=5, value=float(r.precio_actividad or 0))
            ws1.cell(row=fila, column=6, value=float(r.cobrado or 0))
            ws1.cell(row=fila, column=7, value=float(r.porcentaje_lucia or 0))
            ws1.cell(row=fila, column=8, value="SI" if r.recogida_en_coche else "NO")
            ws1.cell(row=fila, column=9, value=float(r.importe_recogida or 0))
            ws1.cell(row=fila, column=10, value=r.monitor_recogida or "")
            ws1.cell(row=fila, column=11, value=r.monitor_experiencia or "")
            ws1.cell(row=fila, column=12, value=float(r.total_experiencia or 0))
            ws1.cell(row=fila, column=13, value=float(r.pago_otros or 0))
            ws1.cell(row=fila, column=14, value=r.codigo_reserva or "")
            ws1.cell(row=fila, column=15, value=r.estado.nombre if r.estado else "")
            ws1.cell(row=fila, column=16, value=r.telefono_cliente or "")
            ws1.cell(row=fila, column=17, value=r.email_cliente or "")
            ws1.cell(row=fila, column=18, value=r.nacionalidad or "")
            ws1.cell(row=fila, column=19, value="; ".join(str(e) for e in (r.edades or [])))
            ws1.cell(row=fila, column=20, value="SI" if r.quiere_transporte else "NO")
            ws1.cell(row=fila, column=21, value=r.direccion_alojamiento or "")
            fila += 1

        # Ajustar ancho de columnas
        anchos = [14, 15, 10, 22, 14, 10, 12, 12, 12, 14, 14, 13, 11, 15, 12, 15, 20, 15, 15, 12, 25]
        for i, ancho in enumerate(anchos, start=1):
            ws1.column_dimensions[get_column_letter(i)].width = ancho

        # ==================================================================
        # Hoja 2: Resumen por plataforma
        # ==================================================================
        ws2 = wb.create_sheet(title="Por plataforma")
        ws2.append(["Plataforma", "Nº reservas", "Total personas", "Total cobrado (€)", "Total experiencia (€)"])

        for celda in ws2[1]:
            celda.font = font_negrita
            celda.fill = relleno_azul
            celda.alignment = alineacion_centro

        resumen_plataformas = (
            reservas.values("plataforma__nombre")
            .annotate(
                num_reservas=Count("id"),
                total_personas=Sum("numero_personas"),
                total_cobrado=Sum("cobrado"),
                total_experiencia=Sum("total_experiencia"),
            )
            .order_by("plataforma__nombre")
        )

        for item in resumen_plataformas:
            ws2.append([
                item["plataforma__nombre"] or "Sin plataforma",
                item["num_reservas"],
                item["total_personas"] or 0,
                round(float(item["total_cobrado"] or 0), 2),
                round(float(item["total_experiencia"] or 0), 2),
            ])

        for i, ancho in enumerate([20, 12, 14, 16, 18], start=1):
            ws2.column_dimensions[get_column_letter(i)].width = ancho

        # ==================================================================
        # Hoja 3: Resumen mensual
        # ==================================================================
        ws3 = wb.create_sheet(title="Resumen mes")
        ws3.append(["Concepto", "Valor"])

        for celda in ws3[1]:
            celda.font = font_negrita
            celda.fill = relleno_azul

        total_cobrado = reservas.aggregate(total=Sum("cobrado"))["total"] or 0
        total_experiencia = reservas.aggregate(total=Sum("total_experiencia"))["total"] or 0
        total_personas = reservas.aggregate(total=Sum("numero_personas"))["total"] or 0
        total_transporte = reservas.filter(quiere_transporte=True).aggregate(
            total=Sum("importe_recogida")
        )["total"] or 0
        total_otros = reservas.aggregate(total=Sum("pago_otros"))["total"] or 0
        total_lucia = round(float(total_cobrado) * 0.0, 2)  # % Lucía ya está por reserva

        filas_resumen = [
            ("Total mes cobrado (€)", round(float(total_cobrado), 2)),
            ("Total experiencia (€)", round(float(total_experiencia), 2)),
            ("TOTAL PERSONAS", int(total_personas or 0)),
            ("Total transporte (€)", round(float(total_transporte), 2)),
            ("Total Otros (€)", round(float(total_otros), 2)),
            ("Nº de reservas", reservas.count()),
        ]

        for concepto, valor in filas_resumen:
            ws3.append([concepto, valor])

        for i, ancho in enumerate([30, 20], start=1):
            ws3.column_dimensions[get_column_letter(i)].width = ancho

        # Guardar archivo
        wb.save(salida)
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Excel exportado: {salida} ({reservas.count()} reservas del {mes:02d}/{anio})"
            )
        )
