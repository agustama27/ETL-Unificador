import csv
import re

target_path = r"c:\Users\agustin.tamagusuku\Downloads\NARANJAX_MA_ROMAN_ALPHA_0405.csv"
test_path = r"c:\Users\agustin.tamagusuku\Downloads\NARANJAX_MA_ROMAN_ALPHA_0405(test).csv"
output_path = r"c:\Users\agustin.tamagusuku\Downloads\NARANJAX_MA_ROMAN_ALPHA_0405(test)_fixed.csv"

# Read target file to get the correct phone numbers (keyed by nombre_cliente)
target_phones = {}
with open(target_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        name = row['nombre_cliente']
        target_phones[name] = {
            'tel_1': row['tel_1'],
            'tel_2': row['tel_2'],
            'tel_3': row['tel_3'],
        }

# Read target headers
with open(target_path, 'r', encoding='utf-8') as f:
    target_headers = f.readline().strip().split(';')

# Read test file - parse manually to handle the extra escenario_prueba column
test_rows = []
with open(test_path, 'r', encoding='utf-8') as f:
    lines = f.read().strip().split('\n')
    test_headers = lines[0].split(';')
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split(';')
        row = {}
        for i, h in enumerate(test_headers):
            row[h] = fields[i] if i < len(fields) else ''
        test_rows.append(row)

# Build output
output_lines = [';'.join(target_headers)]

for row in test_rows:
    nombre = row.get('nombre_cliente', '')
    
    # 1. Fix phone numbers: use target file's values (scientific notation lost precision)
    if nombre in target_phones:
        row['tel_1'] = target_phones[nombre]['tel_1']
        row['tel_2'] = target_phones[nombre]['tel_2']
        row['tel_3'] = target_phones[nombre]['tel_3']
    
    # 2. Fix monto_deuda_nd: empty -> 0.0
    if row.get('monto_deuda_nd', '') == '' or row.get('monto_deuda_nd') is None:
        row['monto_deuda_nd'] = '0.0'
    
    # 3. Fix tipo_marca_plan: "Con" -> "Con Plan", "Sin" -> "Sin Plan"
    tipo = row.get('tipo_marca_plan', '')
    if tipo == 'Con':
        row['tipo_marca_plan'] = 'Con Plan'
    elif tipo == 'Sin':
        row['tipo_marca_plan'] = 'Sin Plan'
    
    # 4. Fix fecha_limite_sistema: DD/MM/YYYY -> YYYY-MM-DD
    fecha = row.get('fecha_limite_sistema', '')
    date_match = re.match(r'(\d{2})/(\d{2})/(\d{4})', fecha)
    if date_match:
        day, month, year = date_match.groups()
        row['fecha_limite_sistema'] = f"{year}-{month}-{day}"
    
    # 5. For "Sin Plan" rows: clear all plan fields to match target format
    if row.get('tipo_marca_plan', '') == 'Sin Plan':
        for i in range(1, 8):
            for suffix in ['cuotas', 'entrega', 'cuota_mensual']:
                key = f'plan_{i}_{suffix}'
                if key in row:
                    row[key] = ''
    
    # 6. For "Con Plan" rows: empty plan_X_entrega should be 0.0
    if row.get('tipo_marca_plan', '') == 'Con Plan':
        for i in range(1, 8):
            cuotas_key = f'plan_{i}_cuotas'
            entrega_key = f'plan_{i}_entrega'
            # Only set entrega to 0.0 if this plan level has cuotas (plan exists)
            if row.get(cuotas_key, '') != '' and row.get(entrega_key, '') == '':
                row[entrega_key] = '0.0'
    
    # 7. Clean any non-numeric data that leaked into plan fields
    #    (escenario_prueba values like 'CON PLAN | TC | tipo=Con' can leak
    #     when the test row has fewer fields than headers)
    for i in range(1, 8):
        for suffix in ['cuotas', 'entrega', 'cuota_mensual']:
            key = f'plan_{i}_{suffix}'
            val = row.get(key, '')
            if val and not re.match(r'^-?\d+\.?\d*$', val):
                row[key] = ''
    
    # Build output line using ONLY target headers (excludes escenario_prueba)
    out_fields = [row.get(h, '') for h in target_headers]
    output_lines.append(';'.join(out_fields))

# Write output
with open(output_path, 'w', encoding='utf-8', newline='') as f:
    f.write('\n'.join(output_lines) + '\n')

print(f"Fixed file written to: {output_path}")
print(f"Total data rows: {len(output_lines) - 1}")

# Verify against target
with open(target_path, 'r', encoding='utf-8') as f:
    target_lines = f.read().strip().split('\n')

print(f"\n--- Verification ---")
print(f"Target columns: {len(target_headers)}")
print(f"Output columns: {len(output_lines[0].split(';'))}")

# Compare ALL rows
match_count = 0
diff_count = 0
for i, (t_line, o_line) in enumerate(zip(target_lines[1:], output_lines[1:])):
    t_fields = t_line.split(';')
    o_fields = o_line.split(';')
    diffs = []
    for j, (tf, of) in enumerate(zip(t_fields, o_fields)):
        if tf != of:
            diffs.append(f"  col {j} ({target_headers[j]}): target='{tf}' vs output='{of}'")
    if diffs:
        diff_count += 1
        print(f"\nRow {i+1} ({o_fields[0]}) differences:")
        for d in diffs:
            print(d)
    else:
        match_count += 1
        print(f"Row {i+1} ({o_fields[0]}): OK MATCH")

print(f"\n--- Summary: {match_count} matches, {diff_count} differences ---")
