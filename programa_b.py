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

def gerar_resposta_orm_B(fluxo, dados):
    """
    fluxo: 'confirmar_cancelamento' (CA) ou 'exame_finalizado' (SC/CM)
    dados: dicionário com a info extraída do pedido original
    """
    emissor, recetor = "PACS", "AIDA"
    data_atual = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Configuração dinâmica baseada no que queremos dizer ao Programa A
    if fluxo == 'confirmar_cancelamento':
        acao = "CA"   # Cancel Order
        estado = ""   # No cancelamento o ORC-5 costuma ir vazio ou repetir CA
        prefixo = "B_CONF_"
    elif fluxo == 'exame_finalizado':
        acao = "SC"   # Status Change
        estado = "CM" # Completed
        prefixo = "B_STAT_"
    else:
        return "Erro: Fluxo de resposta inválido."

    msg_id = f"{prefixo}{data_atual}{random.randint(10, 99)}"

    # Usar o template comum 'mensagens/Pedido.txt'
    try:
        with open('mensagens/Pedido.txt', 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        return "Erro: Ficheiro mensagens/Pedido.txt não encontrado."

    # Preencher o template
    # Nota: No template, o campo ORC deve estar assim: ORC|{acao}|{id_pedido}|{id_pedido}||{estado}||||{data_hoje}|
    mensagem_final = template.format(
        emissor=emissor,
        recetor=recetor,
        data_hoje=data_atual,
        msg_id=msg_id,
        id_paciente=dados["pid"],
        nome_paciente=dados["nome"],
        data_nasc=dados["nasc"],
        sexo=dados["sexo"],
        nif=dados["nif"],
        tipo_paciente=dados["tipo_pac"],
        setor=dados["setor"],
        id_episodio=dados["episodio"],
        acao=acao,
        estado=estado, # Precisas de adicionar {estado} no teu ficheiro .txt
        id_pedido=dados["id_pedido"],
        data_pedido=data_atual,
        cod_exame=dados["cod_exame"],
        desc_exame=dados["desc_exame"],
        extra_obr="|"
    )

    return mensagem_final

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

                # 2. Analisar Tipo e Ação
                linhas = dados.strip().split("\r")
                tipo_msg = extrair_campo(linhas[0], 8) # MSH-9
                dados_lidos = processar_pedido_hl7(dados)
                acao = dados_lidos.get("acao", "")

                # 3. Lógica de Resposta
                
                # CENÁRIO: ADMISSÃO (ADT)
                if "ADT" in tipo_msg:
                    print("-> INFO: Admissão processada. Nenhuma resposta necessária.")

                # CENÁRIO: CANCELAMENTO (ORM-CA)
                elif acao == "CA":
                    print("-> OPERAÇÃO: Cancelamento. Enviando Confirmação...")
                    msg_relatorio = gerar_resposta_orm_B('confirmar_cancelamento', dados_lidos)

                # CENÁRIO: NOVO PEDIDO (ORM-NW)
                elif acao == "NW":
                    print("-> OPERAÇÃO: Novo Pedido. Iniciando fluxo de resposta...")
                    
                    # PASSO 1: Enviar Exame Finalizado (SC / CM)
                    msg_status = gerar_resposta_orm_B('exame_finalizado', dados_lidos)
                    if msg_status:
                        print("   - Enviando Estado: CM (Finalizado)...")
                        enviar_relatorio_para_mirth(msg_status)
                    
                    time.sleep(0.5) # Pausa técnica para o Mirth

                    # PASSO 2: Enviar Relatório de Resultados (ORU^R01)
                    print("   - Enviando Relatório Final (OBX)...")
                    msg_relatorio = criar_relatorio_hl7(
                        dados_lidos["pid"], 
                        dados_lidos["nome"], 
                        dados_lidos["cod_exame"]
                    )
                        
            print("\n ====== Enviando Relatório Final ======= ")
            print(msg_relatorio)
            print("===========================================\n")
            
            enviar_relatorio_para_mirth(msg_relatorio)

#==============================================
# Ponto de entrada do programa
#==============================================
    
if __name__ == "__main__":
    iniciar_programa_b()