import socket
from datetime import datetime
import random
import time

#===============================
#CONFIGURAÇÃO DO SERVIDOR LOCAL
#===============================

# endereco ip local onde o programa B ira receber pedidos
HOST_LOCAL = "127.0.0.1"

# porta onde o programa B ficara a escuta para receber pedidos HL7
PORTA_RECEBER_PEDIDO = 6000

#===============================
# CONFIGURAÇÃO DE LIGAÇÃO AO MIRTH
#===============================

# enderco IP do mirth
MIRTH_HOST = "127.0.0.1"
MIRTH_PORTA_RELATORIO = 5101

#===============================
#CONSTANTES MLLP (protocolo HL7)
#===============================

# Byte de início da mensagem HL7 (MLLP Start Block)
MLLP_START = b"\x0b"

# Bytes de fim de mensagem HL7 (MLLP End Block)
MLLP_END = b"\x1c\x0d"

#==============================================
# FUNCAO PARA ENVOLVER MENSAGEM COM MLLP
#==============================================

def envolver_mllp(mensagem):
    # converte a mensagem para bytes e adiciona delimitadoras de MLLP
    return MLLP_START + mensagem.encode("utf-8") + MLLP_END

#==============================================
# FUNCAO PARA REMOVER MLLP DE UMA MENSAGEM
#==============================================

def remover_mllp(dados):
    # Se começar com byte de início, remove-o
    if dados.startswith(MLLP_START):
        dados = dados[1:]

    # Se terminar com bytes de fim, remove-os
    if dados.endswith(MLLP_END):
        dados = dados[:-2]

    #Converte bytes para string (UTF-8), substituindo erros
    return dados.decode("utf-8", errors="replace")

#==============================================
# FUNCAO auxiliar para extrari campos hl7
#==============================================

def extrair_campo(segmento, indice):
    # divide o segmento pelos separadores "|"
    partes = segmento.split("|")

    # devolver o campor pretendido se existir
    return partes[indice] if len(partes) > indice else ""

#==============================================
# FUNCAO para processar pedido hl7
#==============================================

def processar_pedido_hl7(mensagem):
    linhas = mensagem.strip().split("\r")

    pid=""
    nome=""
    exame = ""

    # percorre cada linha da mensagem
    for linha in linhas:

        #segmento pid (dados do paciente)
        if linha.startswith("PID"):
            pid = extrair_campo(linha, 3) # id do paciente
            nome = extrair_campo(linha, 5) # nome do paciente

        # segmento OBR (pedido de exame)
        elif linha.startswith("OBR"):
            exame = extrair_campo(linha, 4)

    return pid, nome, exame

#==============================================
# FUNCAO para criar relatorio hl7
#==============================================

def criar_relatorio_hl7(pid, nome, exame):
    agora = datetime.now().strftime("%Y%m%d%H%M%S")

    return (
        f"MSH|^~\\&|ProgramaB|Laboratorio|Mirth|Clinica|{agora}||ORU^R01|RPT001|P|2.3\r"
        f"PID|1||{pid}||{nome}||19800101|M\r"
        f"OBR|1||EX001|{exame}|{agora}\r"
        f"OBX|1|TX|RESULTADO||Exame realizado com sucesso. Valores dentro da normalidade. |N\r"
    )

def processar_pedido_hl7(mensagem):
    linhas = mensagem.strip().split("\r")
    dados = {
        "acao": "", "pid": "", "nome": "", "nasc": "", "sexo": "", 
        "nif": "", "tipo_pac": "", "setor": "", "episodio": "", 
        "id_pedido": "", "cod_exame": "", "desc_exame": ""
    }

    for linha in linhas:
        if linha.startswith("PID"):
            dados["pid"] = extrair_campo(linha, 3)
            dados["nome"] = extrair_campo(linha, 5)
            dados["nasc"] = extrair_campo(linha, 7)
            dados["sexo"] = extrair_campo(linha, 8)
            dados["nif"] = extrair_campo(linha, 19)
        elif linha.startswith("PV1"):
            dados["tipo_pac"] = extrair_campo(linha, 2)
            dados["setor"] = extrair_campo(linha, 3)
            dados["episodio"] = extrair_campo(linha, 19)
        elif linha.startswith("ORC"):
            dados["acao"] = extrair_campo(linha, 1) # NW ou CA [cite: 46, 52]
            dados["id_pedido"] = extrair_campo(linha, 2)
        elif linha.startswith("OBR"):
            exame_full = extrair_campo(linha, 4).split("^")
            dados["cod_exame"] = exame_full[0]
            dados["desc_exame"] = exame_full[1] if len(exame_full) > 1 else ""

    return dados

def gerar_resposta_B(fluxo, dados):
    """
    fluxo: 'confirmar_cancelamento', 'exame_finalizado', 'colheita', 'processamento'
    tipo_mensagem: 'ORM^O01' (Radiologia) ou 'OML^O21' (Laboratório)
    """
    emissor, recetor = "PACS", "AIDA"
    data_hoje = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Dicionário de estados para facilitar a lógica
    estados = {
        'confirmar_cancelamento': {'acao': 'CA', 'estado': 'CA', 'prefixo': 'CONF'},
        'exame_finalizado':       {'acao': 'SC', 'estado': 'CM', 'prefixo': 'STAT'},
        'colheita':               {'acao': 'SC', 'estado': 'HC', 'prefixo': 'COLH'},
        'processamento':          {'acao': 'SC', 'estado': 'IP', 'prefixo': 'PROC'}
    }

    config = estados.get(fluxo)
    msg_id = f"B_{config['prefixo']}_{data_hoje}"

    try:
        with open('mensagens/Pedido.txt', 'r', encoding='utf-8') as f:
            template = f.read()
            
        mensagem = template.format(
            emissor=emissor,
            recetor=recetor,
            data_hoje=data_hoje,
            tipo="ORM^O01", # Aqui entra ORM^O01 ou OML^O21
            msg_id=msg_id,
            id_paciente=dados["pid"],
            nome_paciente=dados["nome"],
            data_nasc=dados.get("nasc", ""),
            sexo=dados.get("sexo", ""),
            nif=dados.get("nif", ""),
            tipo_paciente=dados.get("tipo_pac", "I"), # PV1-2 (I ou O)
            setor=dados.get("setor", "RAD"),           # PV1-3 (Ex: INT ou RAD)
            id_episodio=dados.get("episodio", ""),
            id_episodio=dados.get("episodio", ""),
            acao=config['acao'],
            estado=config['estado'], # Garante que o template tem o campo {estado} no ORC
            id_pedido=dados["id_pedido"],
            data_pedido=data_hoje,
            cod_exame=dados["cod_exame"],
            desc_exame=dados["desc_exame"],
            extra_obr="|"
        )
        return mensagem
    except Exception as e:
        print(f"Erro: {e}")
        return None

def gerar_relatorio_B(dados, formato="texto_longo"):
    """
    formato: 'texto_curto' (ST), 'texto_longo' (TX) ou 'pdf' (ED)
    """
    data_atual = datetime.now().strftime("%Y%m%d%H%M%S")
    emissor, recetor = "PACS", "AIDA"
    msg_id = f"RPT_{data_atual}{random.randint(10,99)}"
    
    conteudo_obx = ""

    # --- CASO 1: Texto Curto (Exemplo CLINIDATA / Análises) ---
    if formato == "texto_curto":
        linhas = ["Bla Bla Bla Inicial", "Bla Bla Bla", "Bla Bla Bla Final"]
        for i, texto in enumerate(linhas, 1):
            # ST = String Data, F = Final Result
            conteudo_obx += f"OBX|{i}|ST|BODY||{texto}||||||F|||{data_atual}||^Ana Maria^Frederico\r"

    # --- CASO 2: Texto Longo (Exemplo TAC / Radiologia) ---
    elif formato == "texto_longo":
        linhas = [
            "TAC TORÁCICO", "___", "RELATÓRIO:", 
            "O estudo efectuado foi comparado com exame de 2014...",
            "Não há imagens sugestivas de processos neoformativos.",
            "Relatório validado por: Joaquim Silva"
        ]
        for i, texto in enumerate(linhas, 1):
            # TX = Long Text
            conteudo_obx += f"OBX|{i}|TX|||{texto}||||||F|||{data_atual}\r"

    # --- CASO 3: PDF em Base64 ---
    elif formato == "pdf":
        try:
            # Se tiveres um ficheiro PDF real, podes converter assim:
            # with open("resultado.pdf", "rb") as pdf_file:
            #     encoded_string = base64.b64encode(pdf_file.read()).decode('utf-8')
            
            # Para teste, usamos uma string simulada:
            encoded_string = "JVBERi0xLjQKJ..." 
            conteudo_obx = f"OBX|1|ED|||{encoded_string}||||||F|||{data_atual}"
        except Exception as e:
            print(f"Erro ao processar PDF: {e}")
            return None

    # --- Preencher o Template Final ---
    try:
        with open('mensagens/Relatorio_Base.txt', 'r', encoding='utf-8') as f:
            template = f.read()

        mensagem_final = template.format(
            emissor=emissor,
            recetor=recetor,
            data_hoje=data_atual,
            msg_id=msg_id,
            id_paciente=dados["pid"],
            nome_paciente=dados["nome"],
            data_nasc=dados.get("nasc", ""),
            sexo=dados.get("sexo", ""),
            nif=dados.get("nif", ""),
            tipo_paciente=dados.get("tipo_pac", "I"),
            setor=dados.get("setor", "RAD"),
            id_episodio=dados.get("episodio", ""),
            id_pedido=dados["id_pedido"],
            cod_exame=dados["cod_exame"],
            desc_exame=dados["desc_exame"],
            conteudo_obx=conteudo_obx.strip()
        )
        return mensagem_final
        
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return None
#==============================================
# FUNCAO PARA ENVIAR RELATÓRIO para o mirth
#==============================================

def enviar_relatorio_para_mirth(relatorio):
    # envolve mensagem com mLLP
    pacote = envolver_mllp(relatorio)

    #Debug: mostra primeiros bytes enviados
    print("DEBUG bytes enviados para Mirth:", pacote[:10])

    # cria socket cliente TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:

        # liga ao sesrvidor mirth
        cliente.connect((MIRTH_HOST, MIRTH_PORTA_RELATORIO))

        cliente.sendall(pacote)

    print("Relatorio enviado para o mirth com sucesso.\n")

#==============================================
# FUNCAO princiapl do pragram b
#==============================================
    
def iniciar_programa_b():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        servidor.bind((HOST_LOCAL, PORTA_RECEBER_PEDIDO))

        servidor.listen(1)

        print(f"Programa B à escuta na porta {PORTA_RECEBER_PEDIDO}...")

        while True:
            conn,addr = servidor.accept()

            with conn:
                print(f"Ligacao recebida de {addr}")

                buffer = b""

                while True:
                    chunk = conn.recv(4096)

                    if not chunk:
                        break

                    buffer += chunk

                    if MLLP_END in buffer:
                        break

                dados = remover_mllp(buffer)

                print("\n ====== Mensagem hl7 recebido =======")
                print(dados)
                print("===========================================\n")

                # 1. Identificar Tipo e Ação
                linhas = dados.strip().split("\r")
                tipo_msg = extrair_campo(linhas[0], 8) 
                dados_lidos = processar_pedido_hl7(dados)
                acao = dados_lidos.get("acao", "")
                
                msg_relatorio = None # Variável para guardar o relatório final

                # 2. Lógica de Resposta
                
                # --- CENÁRIO: ADMISSÃO (ADT) ---
                if "ADT" in tipo_msg:
                    print("-> INFO: Admissão processada. Nenhuma resposta necessária.")
                    continue

                # --- CENÁRIO: CANCELAMENTO (ORM-CA) ---
                elif acao == "CA":
                    print("-> OPERAÇÃO: Cancelamento. Enviando Confirmação...")
                    msg_relatorio = gerar_resposta_B('confirmar_cancelamento', dados_lidos, tipo_msg)

                # --- CENÁRIO: NOVO PEDIDO (NW) ---
                elif acao == "NW":
                    print("-> OPERAÇÃO: Novo Pedido. Iniciando fluxo...")
                    
                    # PASSO 1: Enviar Estados Intermédios
                    if "OML" in tipo_msg:
                        # Fluxo de Laboratório
                        enviar_relatorio_para_mirth(gerar_resposta_B('colheita', dados_lidos, "OML^O21"))
                        time.sleep(0.5)
                        enviar_relatorio_para_mirth(gerar_resposta_B('processamento', dados_lidos, "OML^O21"))
                        time.sleep(0.5)
                        enviar_relatorio_para_mirth(gerar_resposta_B('exame_finalizado', dados_lidos, "OML^O21"))
                    else:
                        # Fluxo de Radiologia
                        enviar_relatorio_para_mirth(gerar_resposta_B('exame_finalizado', dados_lidos, "ORM^O01"))

                    time.sleep(0.5)

                    # PASSO 2: Decidir qual Relatório (OBX) gerar usando a nova função
                    print("   - Gerando conteúdo do Relatório Final...")
                    
                    if "OML" in tipo_msg:
                        # Exemplo: Análises usam Texto Curto (ST)
                        msg_relatorio = gerar_relatorio_B(dados_lidos, formato="texto_curto")
                    elif "M10405" in dados_lidos["cod_exame"]:
                        # Exemplo: Se for este código de Raio-X, manda PDF (ED)
                        msg_relatorio = gerar_relatorio_B(dados_lidos, formato="pdf")
                    else:
                        # Padrão para os outros: Texto Longo (TX)
                        msg_relatorio = gerar_relatorio_B(dados_lidos, formato="texto_longo")

                # 3. Envio Final (Confirmação de Cancelamento OU Relatório de Resultados)
                if msg_relatorio:
                    print("\n ====== Enviando Resposta Final ======= ")
                    print(msg_relatorio)
                    print("===========================================\n")
                    enviar_relatorio_para_mirth(msg_relatorio)

#==============================================
# Ponto de entrada do programa
#==============================================
    
if __name__ == "__main__":
    iniciar_programa_b()