import tempfile
import unittest
from pathlib import Path

import pandas as pd

from procesos.base_generator import (
    combinar_archivos,
    generar_csv_telefonos,
    guardar_csv_consolidado,
)


def _crear_estructura_temporal():
    temp_dir = tempfile.TemporaryDirectory()
    base = Path(temp_dir.name)
    (base / 'base-recibida').mkdir(parents=True, exist_ok=True)
    return temp_dir, base


def _guardar_csv(path, filas):
    pd.DataFrame(filas).to_csv(path, sep=';', index=False, encoding='utf-8')


class BaseGeneratorFormatosTest(unittest.TestCase):
    def test_formato_viejo_se_mantiene_compatible(self):
        temp_dir, base = _crear_estructura_temporal()
        self.addCleanup(temp_dir.cleanup)

        _guardar_csv(
            base / 'base-recibida' / 'viejo.csv',
            [
                {
                    'SUMINISTRO': '1001',
                    'CONTRATO': '2',
                    'RAZON_SOCIAL': 'Cliente Viejo',
                    'BARRIO': 'Centro',
                    'DIRECCION': 'Calle 1',
                    'FECHA_EJECUCION': '2026-04-09',
                    'TELEFONO': '3517654321',
                    'TELEFONO_CELULAR': '',
                    'MOTIVO': 'Motivo legacy',
                }
            ],
        )

        df = combinar_archivos(base)

        self.assertEqual(len(df), 1)
        self.assertIn('MOTIVO', df.columns)
        self.assertEqual(df.iloc[0]['MOTIVO'], 'Motivo legacy')
        self.assertEqual(df.iloc[0]['CONNECTION_RESULT'], 'CXI')

    def test_formato_nuevo_mapea_descripcion_completa_a_motivo(self):
        temp_dir, base = _crear_estructura_temporal()
        self.addCleanup(temp_dir.cleanup)

        _guardar_csv(
            base / 'base-recibida' / 'nuevo.csv',
            [
                {
                    'SUMINISTRO': '2002',
                    'CONTRATO': '5',
                    'RAZON_SOCIAL': 'Cliente Nuevo',
                    'BARRIO': 'Nueva Cordoba',
                    'DIRECCION': 'Calle 2',
                    'FECHA_EJECUCION': '2026-04-09',
                    'TELEFONO': '',
                    'TELEFONO_CELULAR': '3511234567',
                    'COSTO_INSTALACION': 51456,
                    'GASTO_MOVILIDAD': 28610,
                    'DESCRIPCION_COMPLETA': 'No se ubicó encargado',
                }
            ],
        )

        df = combinar_archivos(base)

        self.assertEqual(len(df), 1)
        self.assertIn('MOTIVO', df.columns)
        self.assertNotIn('DESCRIPCION_COMPLETA', df.columns)
        self.assertEqual(df.iloc[0]['MOTIVO'], 'No se ubicó encargado')
        self.assertEqual(df.iloc[0]['CONNECTION_RESULT'], 'CXI')

    def test_columnas_nuevas_se_procesan_y_llegan_a_salida(self):
        temp_dir, base = _crear_estructura_temporal()
        self.addCleanup(temp_dir.cleanup)

        _guardar_csv(
            base / 'base-recibida' / 'nuevo.csv',
            [
                {
                    'SUMINISTRO': '3003',
                    'CONTRATO': '7',
                    'RAZON_SOCIAL': 'Cliente Costos',
                    'BARRIO': 'General Paz',
                    'DIRECCION': 'Calle 3',
                    'FECHA_EJECUCION': '2026-04-09',
                    'TELEFONO': '3516543210',
                    'TELEFONO_CELULAR': '',
                    'COSTO_INSTALACION': 89147,
                    'GASTO_MOVILIDAD': 28610,
                    'DESCRIPCION_COMPLETA': 'Otro problema',
                }
            ],
        )

        df = combinar_archivos(base)

        self.assertIn('COSTO_INSTALACION', df.columns)
        self.assertIn('GASTO_MOVILIDAD', df.columns)
        self.assertEqual(float(df.iloc[0]['COSTO_INSTALACION']), 89147.0)
        self.assertEqual(float(df.iloc[0]['GASTO_MOVILIDAD']), 28610.0)

    def test_compatibilidad_con_formatos_viejo_y_nuevo(self):
        temp_dir, base = _crear_estructura_temporal()
        self.addCleanup(temp_dir.cleanup)

        _guardar_csv(
            base / 'base-recibida' / 'viejo.csv',
            [
                {
                    'SUMINISTRO': '4004',
                    'CONTRATO': '9',
                    'RAZON_SOCIAL': 'Legacy',
                    'BARRIO': 'Centro',
                    'DIRECCION': 'Calle 4',
                    'FECHA_EJECUCION': '2026-04-09',
                    'TELEFONO': '3519990000',
                    'TELEFONO_CELULAR': '',
                    'MOTIVO': 'Motivo viejo',
                }
            ],
        )
        _guardar_csv(
            base / 'base-recibida' / 'nuevo.csv',
            [
                {
                    'SUMINISTRO': '5005',
                    'CONTRATO': '11',
                    'RAZON_SOCIAL': 'Nuevo',
                    'BARRIO': 'Alta Cordoba',
                    'DIRECCION': 'Calle 5',
                    'FECHA_EJECUCION': '2026-04-09',
                    'TELEFONO': '',
                    'TELEFONO_CELULAR': '3517778888',
                    'COSTO_INSTALACION': 12345,
                    'GASTO_MOVILIDAD': 6789,
                    'DESCRIPCION_COMPLETA': 'Descripcion nueva',
                }
            ],
        )

        df = combinar_archivos(base)

        self.assertEqual(len(df), 2)
        self.assertIn('MOTIVO', df.columns)
        motivos = set(df['MOTIVO'].tolist())
        self.assertIn('Motivo viejo', motivos)
        self.assertIn('Descripcion nueva', motivos)

    def test_formato_con_ord_fecha_fin_se_normaliza_a_fecha_ejecucion(self):
        temp_dir, base = _crear_estructura_temporal()
        self.addCleanup(temp_dir.cleanup)

        _guardar_csv(
            base / 'base-recibida' / 'nuevo_ord.csv',
            [
                {
                    'SUMINISTRO': '5100',
                    'CONTRATO': '15',
                    'RAZON_SOCIAL': 'Cliente Ord',
                    'BARRIO': 'Alta Cordoba',
                    'DIRECCION': 'Calle 51',
                    'ORD_FECHA_FIN': '2026-04-14',
                    'TELEFONO': '',
                    'TELEFONO_CELULAR': '3517779999',
                    'MOTIVO': 'Fin de orden',
                }
            ],
        )

        df = combinar_archivos(base)

        self.assertIn('FECHA_EJECUCION', df.columns)
        self.assertNotIn('ORD_FECHA_FIN', df.columns)
        self.assertEqual(df.iloc[0]['FECHA_EJECUCION'], '2026-04-14')

    def test_salida_base_epec_aplica_esquema_final(self):
        temp_dir, base = _crear_estructura_temporal()
        self.addCleanup(temp_dir.cleanup)

        _guardar_csv(
            base / 'base-recibida' / 'viejo.csv',
            [
                {
                    'SUMINISTRO': '6006',
                    'CONTRATO': '12',
                    'RAZON_SOCIAL': 'Cliente Salida',
                    'BARRIO': 'Jardin',
                    'DIRECCION': 'Calle 6',
                    'FECHA_EJECUCION': '2026-04-09',
                    'TELEFONO': '3511231234',
                    'TELEFONO_CELULAR': '',
                    'MOTIVO': 'Validar cabecera',
                }
            ],
        )

        df = combinar_archivos(base)
        archivo = guardar_csv_consolidado(df, base, nombre_archivo='base_epec_test.csv')
        salida = pd.read_csv(archivo, sep=';', dtype=str).fillna('')

        columnas_esperadas = [
            'nombre_cliente',
            'telefono',
            'telefono_celular',
            'contrato',
            'dia_visita',
            'motivo',
            'direccion',
            'resultado_solicitud',
            'medidor',
            'dia_gestion',
            'suministro',
            'costo_instalacion',
            'gasto_movilidad',
        ]

        self.assertEqual(list(salida.columns), columnas_esperadas)
        self.assertEqual(salida.iloc[0]['nombre_cliente'], 'Cliente Salida')
        self.assertEqual(salida.iloc[0]['telefono'], '543511231234')
        self.assertEqual(salida.iloc[0]['telefono_celular'], '')
        self.assertEqual(salida.iloc[0]['contrato'], '12')
        self.assertEqual(salida.iloc[0]['motivo'], 'Validar cabecera')
        self.assertEqual(salida.iloc[0]['direccion'], 'Calle 6')
        self.assertEqual(salida.iloc[0]['resultado_solicitud'], 'CXI')
        self.assertEqual(salida.iloc[0]['dia_gestion'], '2026-04-09')
        self.assertEqual(salida.iloc[0]['suministro'], '6006')
        self.assertEqual(salida.iloc[0]['dia_visita'], '')
        self.assertEqual(salida.iloc[0]['medidor'], '')


class BaseGeneratorTelefonosEpecTest(unittest.TestCase):
    def test_telefonos_epec_normaliza_valida_y_deduplica(self):
        temp_dir, base = _crear_estructura_temporal()
        self.addCleanup(temp_dir.cleanup)

        df = pd.DataFrame(
            [
                {'TELEFONO': '3517654321', 'TELEFONO_CELULAR': ''},
                {'TELEFONO': '543517654322', 'TELEFONO_CELULAR': ''},
                {'TELEFONO': '(351) 333-4444', 'TELEFONO_CELULAR': ''},
                {'TELEFONO': '1234', 'TELEFONO_CELULAR': ''},
                {'TELEFONO': '1111111111', 'TELEFONO_CELULAR': ''},
                {'TELEFONO': '3517778888', 'TELEFONO_CELULAR': ''},
                {'TELEFONO': '3517778888', 'TELEFONO_CELULAR': ''},
                {'TELEFONO': '', 'TELEFONO_CELULAR': '3511234567'},
                {'TELEFONO': '', 'TELEFONO_CELULAR': '5493511234568'},
                {'TELEFONO': '', 'TELEFONO_CELULAR': '12-34'},
                {'TELEFONO': '', 'TELEFONO_CELULAR': '1234567890'},
            ]
        )

        archivo = generar_csv_telefonos(df, base)
        salida = pd.read_csv(archivo, sep=';', dtype=str).fillna('')

        self.assertEqual(list(salida.columns), ['NumeroTelefono', 'NumeroCelular'])

        telefonos = set(salida['NumeroTelefono'].tolist()) - {''}
        celulares = set(salida['NumeroCelular'].tolist()) - {''}

        self.assertIn('543517654321', telefonos)  # prefijo fijo agregado
        self.assertIn('543517654322', telefonos)  # no doble prefijo fijo
        self.assertIn('543513334444', telefonos)  # no numericos removidos

        self.assertIn('5493511234567', celulares)  # prefijo celular agregado
        self.assertIn('5493511234568', celulares)  # no doble prefijo celular

        self.assertNotIn('541234', telefonos)  # longitud invalida
        self.assertNotIn('541111111111', telefonos)  # patron trivial invalido
        self.assertNotIn('5491234567890', celulares)  # secuencia trivial invalida
        self.assertNotIn('543517778888', telefonos)  # duplicado excluido

        todos = [n for n in salida['NumeroTelefono'].tolist() + salida['NumeroCelular'].tolist() if n]
        self.assertEqual(len(todos), len(set(todos)))


if __name__ == '__main__':
    unittest.main()
