import asyncio
import re
import requests
import pdfplumber
import pprint
from playwright.async_api import async_playwright
from typing import List

BASE_URL = "https://dje.tjsp.jus.br" # Define a URL base do DJE

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

# async def obter_url_pdf(page) -> str:
#     """Obtém a URL do PDF a partir do atributo onclick do link de visualização."""
#     await page.click('input[type="submit"]')
#     await page.wait_for_selector('a.layout[title="Visualizar"]')
#     onclick_attr = await page.get_attribute('a.layout[title="Visualizar"]', 'onclick')
#     if not onclick_attr:
#         raise ValueError("Atributo 'onclick' não encontrado no link de visualização.")

#     match = re.search(r"popup\('([^']+)'\)", onclick_attr)
#     if not match:
#         raise ValueError("URL do PDF não encontrada no atributo 'onclick'.")

#     url_relativa = match.group(1).lstrip('/')
#     return f"{BASE_URL}/{url_relativa}"

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

def baixar_pdf(url: str, caminho_arquivo: str) -> None:
    """Baixa o PDF da URL especificada e salva no caminho fornecido."""
    url = url.replace("consultaSimples", "getPaginaDoDiario")
    url = f"{url}&uuidCaptcha="
    print(url)
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
    else:
        print("Número do processo não encontrado.")

# Função padrão que engloba as outras funções que fazem os processos de captura
async def main():
    data_inicio = "13/11/2024"
    data_fim = "13/11/2024"
    caderno = "12" # Caderno a ser pesquisado os termos
    termo_busca = '"RPV" e "pagamento pelo INSS"' # Termo a ser buscado na pesquisa avançada do DJE
    caminho_pdf = "pagina.pdf" # Caminho para salvar a pagina do PDF
    processos_encontrados = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Inicia um novo navegador
        page = await browser.new_page() # Abre uma página (guia) no navegador

        try:
            # Faz o preenchimento do formulário
            await preencher_formulario(page, data_inicio, data_fim, caderno, termo_busca)

            # Obtem a URL do PDF localizado na pesquisa
            url_pdf = await obter_url_pdf(page)
            # pprint.pprint(f"URL do PDF: {url_pdf}")

            for url in url_pdf:
                print(f"URL Atual: {url}")

                # Baixa o PDF para poder ser analisado localmente
                baixar_pdf(url, caminho_pdf)
                print("PDF baixado com sucesso.")

                # Extrai o texto do PDF para poder ser tratado e filtrado
                texto_pdf = extrair_texto_pdf(caminho_pdf)

                # Quebra o texto do PDF para poder facilitar e ter busca bloco por bloco de processo
                arr_textos = texto_pdf.split("\nProcesso ", -1)

                # Varre o array de textos (processos) para verificar se existe os termos a serem pesquisados e se tiver capturar o numero do processo
                for texto in arr_textos:
                    if "rpv" in texto.lower() and "pagamento pelo inss" in texto.lower():
                        numero_processo = extrair_numero_processo(texto)
                        processos_encontrados.append({
                            "numero_processo": numero_processo,
                            "data_disponibilizacao": "teste", 
                            "autores": [],
                            "advogados": [],
                            "conteudo": "",
                            "valor_principal_bruto_liquido": 0,
                            "valor_juros_moratorios": 0,
                            "honorários_advocaticios": 0
                        })
                        # print(f"Numero Processo: {numero_processo}")

            pprint.pprint(f"Processos localizados: {processos_encontrados}")

        except Exception as e:
            print(f"Ocorreu um erro: {e}")

        finally:
            await browser.close()

# Inicia a automação por aqui
if __name__ == "__main__":
    asyncio.run(main())
