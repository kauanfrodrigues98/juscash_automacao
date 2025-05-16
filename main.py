import asyncio
import re
import requests
import pdfplumber
import locale
from playwright.async_api import async_playwright
from typing import List
from datetime import datetime
from queries import salvar_processos, salvar_caderno

BASE_URL: str = "https://dje.tjsp.jus.br" # Define a URL base do DJE
CAMINHO_PDF: str = "downloads/pagina.pdf" # Caminho para salvar a pagina do PDF
PROCESSOS_ENCONTRADOS = []
CONTEUDO_CADERNO = []

# Função responsável por preencher o formulário do DJE
async def preencher_formulario(page, data_inicio: str, data_fim: str, caderno: str, termo_busca: str):
    # Navega até a página do DJE de SP
    await page.goto(f"{BASE_URL}/cdje/index.do")

    # Altera a data de inicio
    await page.wait_for_selector("#dtInicioString")
    await page.eval_on_selector("#dtInicioString", "el => el.removeAttribute('readonly')")
    await page.fill("#dtInicioString", data_inicio)

    # Altera a data final
    await page.wait_for_selector("#dtFimString")
    await page.eval_on_selector("#dtFimString", "el => el.removeAttribute('readonly')")
    await page.fill("#dtFimString", data_fim)

    # Seleciona o caderno
    await page.select_option("[name='dadosConsulta.cdCaderno']", value=caderno)

    # Preenche o termo de busca avançada
    await page.wait_for_selector("#procura")
    await page.fill("#procura", termo_busca)

async def obter_url_pdf(page) -> List[str]:
    """Obtém todas as URLs de PDFs a partir dos atributos onclick dos links de visualização."""
    await page.click('input[type="submit"]')
    await page.wait_for_selector('a.layout[title="Visualizar"]')

    # Localiza todos os links com o título "Visualizar"
    links = await page.locator('a.layout[title="Visualizar"]').all()

    urls = []
    for link in links:
        onclick_attr = await link.get_attribute('onclick')
        if onclick_attr:
            match = re.search(r"popup\('([^']+)'\)", onclick_attr)
            if match:
                url_relativa = match.group(1).lstrip('/')
                urls.append(f"{BASE_URL}/{url_relativa}")

    if not urls:
        raise ValueError("Nenhuma URL de PDF encontrada.")

    return urls

async def obter_url_pdf_proximo(page) -> List[str]:
    """Obtém todas as URLs de PDFs a partir dos atributos onclick dos links de visualização."""
    await page.wait_for_selector('a[title="Visualizar"]')

    # Localiza todos os links com o título "Visualizar"
    links = await page.locator('a[title="Visualizar"]').all()

    urls = []
    for link in links:
        onclick_attr = await link.get_attribute('onclick')
        if onclick_attr:
            match = re.search(r"popup\('([^']+)'\)", onclick_attr)
            if match:
                url_relativa = match.group(1).lstrip('/')
                urls.append(f"{BASE_URL}/{url_relativa}")

    if not urls:
        raise ValueError("Nenhuma URL de PDF encontrada.")

    return urls

def baixar_pdf(url: str, caminho_arquivo: str) -> None:
    """Baixa o PDF da URL especificada e salva no caminho fornecido."""
    url = url.replace("consultaSimples", "getPaginaDoDiario")
    url = f"{url}&uuidCaptcha="
    # print(url)
    response = requests.get(url)
    if response.status_code != 200:
        raise ConnectionError(f"Falha ao baixar o PDF. Status code: {response.status_code}")
    with open(caminho_arquivo, "wb") as f:
        f.write(response.content)

def extrair_texto_pdf(caminho_arquivo: str) -> str:
    """Extrai o texto de todas as páginas do PDF."""
    texto = ""
    with pdfplumber.open(caminho_arquivo) as pdf:
        for pagina in pdf.pages:
            pagina_texto = pagina.extract_text()
            if pagina_texto:
                texto += pagina_texto + "\n"
    return texto

def extrair_numero_processo(texto: str) -> str:
    padrao = r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}'

    resultado = re.search(padrao, texto)

    if resultado:
        numero_processo = resultado.group()
        return numero_processo
    # else:
    #     print("Número do processo não encontrado.")

def extrair_disponibilizacao(texto: str):
    padrao = r"Disponibilização:\s*(\w+-feira),\s*(\d{1,2}) de (\w+) de (\d{4})"
    match = re.search(padrao, texto, re.IGNORECASE)

    if match:
        dia_semana, dia, mes, ano = match.groups()

        # Configura o locale para português do Brasil
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

        # Monta a estrutura da data a ser formatada
        data_str = f"{dia} de {mes} de {ano}"

        # Converte a string para um objeto datetime
        data_obj = datetime.strptime(data_str, "%d de %B de %Y")

        # Formata o objeto datetime para o formato dd/mm/yyyy
        return data_obj.strftime("%d/%m/%Y")
    # else:
    #     print("Data de disponibilização não encontrada.")

# Extrai o valor principal bruto/liquido do processo
def extrair_valor_principal(texto: str) -> str:
    padrao = r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}\s*-\s*principal bruto/líquido;'
    resultado = re.findall(padrao, texto)
    if resultado:
        return resultado[0].split(" -", -1)[0]
    # print("Valor principal não encontrado.")
    return None

# Extrai o valor de juros moratórios
def extrair_valor_juros_moratorios(texto: str) -> str:
    padrao = r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}\s*-\s*juros moratórios;'
    resultado = re.findall(padrao, texto)
    if resultado:
        return resultado[0].split(" -", -1)[0]
    # print("Valor de juros moratórios não encontrado.")
    return None

# Extrai o honorário advocaticio do processo
def extrair_honorarios_advocaticios(texto: str) -> str:
    padrao = r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}\s*-\s*honorários advocatícios'
    resultado = re.findall(padrao, texto)
    if resultado:
        return resultado[0].split(" -", -1)[0]
    # print("Valor de honorários não encontrado.")
    return None

# Extrai os autores do processo
def extrair_autores(texto: str) -> str:
    arr_texto = texto.split(" - ", 5)
    if len(arr_texto) > 3:
        return arr_texto[3]
    # print("Autores não encontrados.")
    return None

# Extrai os advogados do processo
def extrair_advogados(texto: str) -> str:
    match = re.search(r"ADV:\s*(.*)", texto, re.DOTALL)

    if match:
        advogados = match.group(1).strip()
        return advogados
    # else:
    #     print("Nenhum advogado encontrado.")
    return None

# Processa as páginas para captura dos dados
async def processar_paginas(urls_pdf):
    for url in urls_pdf:
        # Baixa o PDF para poder ser analisado localmente
        baixar_pdf(url, CAMINHO_PDF)

        # Extrai o texto do PDF para poder ser tratado e filtrado
        texto_pdf = extrair_texto_pdf(CAMINHO_PDF)

        data_disponibilizacao = extrair_disponibilizacao(texto_pdf)

        # Quebra o texto do PDF para poder facilitar e ter busca bloco por bloco de processo
        arr_textos = texto_pdf.split("\nProcesso ", -1)

        CONTEUDO_CADERNO.append({
            texto_pdf,
            data_disponibilizacao
        })

        # Varre o array de textos (processos) para verificar se existe os termos a serem pesquisados e se tiver capturar o numero do processo
        for texto in arr_textos:
            if "rpv" in texto.lower() and "pagamento pelo inss" in texto.lower():
                try:
                    numero_processo = extrair_numero_processo(texto)
                    autores = extrair_autores(texto)
                    advogados = extrair_advogados(texto)
                    valor_principal_bruto_liquido = extrair_valor_principal(texto)
                    valor_juros_moratorios = extrair_valor_juros_moratorios(texto)
                    honorarios_advocaticios = extrair_honorarios_advocaticios(texto)

                    data_convertida = datetime.strptime(data_disponibilizacao, "%d/%m/%Y").date()

                    # Transforma para string no formato ISO (yyyy-mm-dd) se necessário
                    # data_convertida = data_convertida.date() 

                    PROCESSOS_ENCONTRADOS.append({
                        "numero_processo": numero_processo,
                        "data_disponibilizacao": data_convertida,
                        "autores": autores,
                        "advogados": advogados,
                        # "conteudo": texto_pdf,
                        "valor_principal_bruto_liquido": valor_principal_bruto_liquido,
                        "valor_juros_moratorios": valor_juros_moratorios,
                        "honorarios_advocaticios": honorarios_advocaticios
                    })
                except Exception as e:
                    print(f"Erro ao processar um processo: {e}")

# Função padrão que engloba as outras funções que fazem os processos de captura
async def main():
    data_inicio = "13/11/2024"
    data_fim = "13/11/2024"
    caderno = "12" # Caderno a ser pesquisado os termos
    termo_busca = '"RPV" e "pagamento pelo INSS"' # Termo a ser buscado na pesquisa avançada do DJE

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Inicia um novo navegador
        page = await browser.new_page() # Abre uma página (guia) no navegador

        try:
            # Faz o preenchimento do formulário
            await preencher_formulario(page, data_inicio, data_fim, caderno, termo_busca)

            urls_pdf = await obter_url_pdf(page)

            urls_pdf = list(dict.fromkeys(urls_pdf))

            await processar_paginas(urls_pdf)

            # Enquanto existir o elemento Próximo> na tela, significa que existem paginas a mais para serem processadas
            while await page.get_by_text('Próximo>').count() > 0:
                try:
                    # Obtem a URL do PDF localizado na pesquisa
                    await page.locator('text=Próximo>').first.click()

                    await asyncio.sleep(3) # Executa um sleep de 5 segundos para poder dar tempo de atualizar os elementos da tela e poder capturar corretamente

                    urls_pdf = await obter_url_pdf_proximo(page)

                    urls_pdf = list(dict.fromkeys(urls_pdf))

                    await processar_paginas(urls_pdf)  # Certifique-se que essa função esteja correta
                except Exception as e:
                    print(f"Erro ao clicar no botão 'Próximo>': {e}")
                    break

            print("Processou tudo!")

            for caderno in CONTEUDO_CADERNO:
                caderno_id = await salvar_caderno(caderno)

                for processo in PROCESSOS_ENCONTRADOS:
                    if processo["numero_processo"]:
                        await salvar_processos(caderno_id, processo)

        except Exception as e:
            print(f"Ocorreu um erro: {e}")

        finally:
            await browser.close()

# Inicia a automação por aqui
if __name__ == "__main__":
    asyncio.run(main())
