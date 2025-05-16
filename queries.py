from database import get_connection

def buscar_processos():
    conn = get_connection()
    
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM processos")
    resultados = cur.fetchall()

    cur.close()
    conn.close()

    return resultados

async def salvar_caderno(caderno):
    try:
        conn = get_connection()

        if not conn:
            return []
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO processos (
                data_disponibilizacao,
                conteudo
            ) VALUES (%s, %s)
            RETURNING id
        """, (
            caderno['data_disponibilizacao'],
            caderno['texto_pdf'],
        ))

        caderno_id = cur.fetchone()[0]
        conn.commit()

        cur.close()
        conn.close()

        return caderno_id
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

async def salvar_processos(caderno_id, processo):
    try:
        conn = get_connection()

        if not conn:
            return []
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO processos (
                caderno,
                numero_processo, 
                autores, 
                advogados, 
                valor_principal_bruto_liquido, 
                valor_juros_moratorios, 
                honorarios_advocaticios
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            caderno_id,
            processo['numero_processo'],
            processo['autores'],
            processo['advogados'], 
            processo['valor_principal_bruto_liquido'],
            processo['valor_juros_moratorios'],
            processo['honorarios_advocaticios']
        ))
        conn.commit()

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Ocorreu um erro: {e}")