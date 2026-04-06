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
# GUARDAR OS PACIENTES
#==============================================

import json
import os

FICHEIRO_PACIENTES = "pacientes.json"

def carregar_pacientes():
    if not os.path.exists(FICHEIRO_PACIENTES):
        return {}
    try:
        with open(FICHEIRO_PACIENTES, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def guardar_pacientes(pacientes):
    with open(FICHEIRO_PACIENTES, "w", encoding="utf-8") as f:
        json.dump(pacientes, f, indent=4)

#==============================================
# FUNCAO PARA GUARDAR HISTORICO (BASE DE DADOS SIMULADA)
#==============================================

def guardar_historico(dados, estado="Concluído"):
    data_registo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{data_registo}] PID: {dados['pid']} | Nome: {dados['nome']} | Exame: {dados['desc_exame']} | Estado: {estado}\n"
    with open("historico_exames.txt", "a", encoding="utf-8") as f:
        f.write(linha)

#==============================================
# FUNCAO auxiliar para extrari campos hl7
#==============================================

def extrair_campo(segmento, indice):
    # divide o segmento pelos separadores "|"
    partes = segmento.split("|")

    # devolver o campor pretendido se existir
    return partes[indice] if len(partes) > indice else ""


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


#==============================================
# FUNCAO para processar pedido hl7
#==============================================


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

def gerar_resposta_B(fluxo, dados, tipo_mensagem="ORM^O01"):
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
            tipo=tipo_mensagem, # Aqui entra ORM^O01 ou OML^O21
            msg_id=msg_id,
            id_paciente=dados["pid"],
            nome_paciente=dados["nome"],
            data_nasc=dados.get("nasc", ""),
            sexo=dados.get("sexo", ""),
            nif=dados.get("nif", ""),
            tipo_paciente=dados.get("tipo_pac", "I"), 
            setor=dados.get("setor", "RAD"),           
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
    
    # --- 1. DEFINIÇÃO DOS CONTEÚDOS POR EXAME ---
    # Podes adicionar quantos códigos quiseres aqui
    biblioteca_laudos = {
        "M10405": {
            "titulo": "RAIO-X AO TÓRAX (PA/PERFIL)",
            "linhas": [
                "Campos pleuro-pulmonares com transparência normal.",
                "Índice cardiotorácico dentro dos limites da normalidade.",
                "Seios costo-frénicos livres.",
                "CONCLUSÃO: Exame sem evidência de patologia aguda."
            ],
            "formato": "texto_longo"
        },
        "TAC01": {
            "titulo": "TAC ABDOMINAL COM CONTRASTE",
            "linhas": [
                "Fígado de dimensões e contornos normais.",
                "Ausência de lesões focais ou líquido livre intra-abdominal.",
                "Vias biliares não dilatadas.",
                "Pâncreas e baço sem alterações morfológicas."
            ],
            "formato": "texto_longo"
        },
        "ANAL01": {
            "titulo": "HEMOGRAMA COMPLETO",
            "linhas": [
                "Leucócitos: 6.500 /mm3",
                "Hemoglobina: 14.2 g/dL",
                "Plaquetas: 210.000 /mm3"
            ],
            "formato": "texto_curto"
        }
    }

    # --- 2. SELEÇÃO DO CONTEÚDO ---
    codigo = dados.get("cod_exame", "")
    # Se o código existir na biblioteca, usa. Senão, usa um padrão genérico.
    laudo_selecionado = biblioteca_laudos.get(codigo, {
        "titulo": "RELATÓRIO DE EXAME GERAL",
        "linhas": ["Exame realizado com sucesso.", "Sem observações críticas a registar."],
        "formato": "texto_longo"
    })

    conteudo_obx = ""
    tipo_hl7 = "TX" if laudo_selecionado["formato"] == "texto_longo" else "ST"

    # Adiciona o Título como primeira linha do OBX
    conteudo_obx += f"OBX|1|{tipo_hl7}|||{laudo_selecionado['titulo']}||||||F|||{data_atual}\r"

    # Adiciona as linhas do laudo
    for i, texto in enumerate(laudo_selecionado["linhas"], 2):
        conteudo_obx += f"OBX|{i}|{tipo_hl7}|||{texto}||||||F|||{data_atual}\r"

    # --- Preencher o Template Final ---
    try:
        with open('mensagens/Relatorio.txt', 'r', encoding='utf-8') as f:
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
                    subtipo = ""
                    # Tenta extrair o subtipo (A08 ou A40) do MSH-9
                    msh_9 = extrair_campo(linhas[0], 8)
                    if "^" in msh_9:
                        subtipo = msh_9.split("^")[1]

                    pacientes = carregar_pacientes()
                    pid_principal = dados_lidos["pid"]

                    if subtipo == "A40":
                        # LÓGICA A40: FUSÃO (Mover dados do antigo para o novo)
                        id_antigo = ""
                        for l in linhas:
                            if l.startswith("MRG"):
                                id_antigo = extrair_campo(l, 1)
                        
                        print(f"--- FUSÃO (A40) ---")
                        print(f"A remover ID antigo: {id_antigo}")
                        if id_antigo in pacientes:
                            del pacientes[id_antigo]
                        print(f"A associar dados ao ID principal: {pid_principal}")
                        
                    elif subtipo == "A08":
                        # LÓGICA A08: ATUALIZAÇÃO
                        print(f"--- ATUALIZAÇÃO (A08) ---")
                        print(f"A atualizar dados do paciente: {pid_principal}")

                    # Em ambos os casos, guardamos/atualizamos o registo principal
                    pacientes[pid_principal] = {
                        "nome": dados_lidos["nome"],
                        "nasc": dados_lidos["nasc"],
                        "sexo": dados_lidos["sexo"],
                        "nif": dados_lidos["nif"]
                    }
                    guardar_pacientes(pacientes)
                    print(f"✔ JSON atualizado com sucesso para {dados_lidos['nome']}.\n")
                    
                    # Como não queres ACK, fazemos apenas 'continue' para esperar a próxima mensagem
                    continue
            
                # --- CENÁRIO: CANCELAMENTO (ORM-CA) ---
                elif acao == "CA":
                    print("-> OPERAÇÃO: Cancelamento. Enviando Confirmação...")
                    msg_relatorio = gerar_resposta_B('confirmar_cancelamento', dados_lidos, tipo_msg)

                # --- CENÁRIO: NOVO PEDIDO (NW) ---
                elif acao == "NW":
                    pacientes = carregar_pacientes()

                    pid = dados_lidos["pid"]

                    if pid not in pacientes:
                        print(f" Novo paciente {pid} detetado no pedido → a criar automaticamente.")
                    else:
                        print(f" Paciente {pid} já existe → dados podem ser atualizados.")
                        
                    # Criar ou atualizar paciente automaticamente com os dados do pedido
                    pacientes[pid] = {
                        "nome": dados_lidos["nome"],
                        "nasc": dados_lidos["nasc"],
                        "sexo": dados_lidos["sexo"],
                        "nif": dados_lidos["nif"]
                    }

                    guardar_pacientes(pacientes)

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
                    
                    # Deixa a função decidir tudo sozinha com base no dicionário que criámos
                    msg_relatorio = gerar_relatorio_B(dados_lidos)

                # 3. Envio Final (Confirmação de Cancelamento OU Relatório de Resultados)
                if msg_relatorio:
                    print("\n ====== Enviando Resposta Final ======= ")
                    print(msg_relatorio)
                    print("===========================================\n")
                    enviar_relatorio_para_mirth(msg_relatorio)

                    # 4. GUARDAR NA "BASE DE DADOS"
                    if acao == "NW":
                        guardar_historico(dados_lidos, estado="Exame Concluído")
                        print("-> [REGISTO] Exame guardado na base de dados (historico_exames.txt).")
                    elif acao == "CA":
                        guardar_historico(dados_lidos, estado="Cancelado")
                        print("-> [REGISTO] Cancelamento guardado na base de dados (historico_exames.txt).")
#==============================================
# Ponto de entrada do programa
#==============================================
    
if __name__ == "__main__":
    iniciar_programa_b()